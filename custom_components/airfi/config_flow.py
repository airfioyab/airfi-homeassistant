"""Config flow and options flow for the Airfi integration."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_TYPE,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .discovery import DiscoveredDevice, async_discover_devices
from .modbus import AirfiConnectionError, AirfiModbusClient, AirfiModbusError

_PORT_SELECTOR = vol.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=65535, step=1, mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Coerce(int),
)

STEP_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): _PORT_SELECTOR,
    }
)


async def _validate_connection(host: str, port: int) -> str | None:
    """Try reading input register 1; return an error key or None."""
    client = AirfiModbusClient(host, port)
    try:
        await client.read_input_register(1)
    except AirfiConnectionError:
        return "cannot_connect"
    except AirfiModbusError:
        return "modbus_error"
    return None


class AirfiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Discover-or-manual config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._devices: dict[str, DiscoveredDevice] = {}
        self._discovery_task: asyncio.Task[list[DiscoveredDevice]] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer discovery or manual entry."""
        return self.async_show_menu(
            step_id="user", menu_options=["discover", "manual"]
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Listen for announcements, then present the found devices."""
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(
                async_discover_devices()
            )
        if not self._discovery_task.done():
            return self.async_show_progress(
                step_id="discover",
                progress_action="discovering",
                progress_task=self._discovery_task,
            )

        try:
            devices = self._discovery_task.result()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Discovery failed")
            devices = []

        known_ids = self._async_current_ids(include_ignore=True)
        # Exclude by host regardless of configured port: a device reachable
        # through a non-default port (NAT/port-forward, simulator) is still
        # the same device, and offering it again would create a duplicate
        # entry fighting over the single-client Modbus socket.
        known_hosts = {
            entry.data.get(CONF_HOST)
            for entry in self._async_current_entries(include_ignore=True)
        }
        self._devices = {
            str(dev.serial): dev
            for dev in devices
            if str(dev.serial) not in known_ids and dev.ip not in known_hosts
        }
        if not self._devices:
            return self.async_show_progress_done(next_step_id="manual")
        return self.async_show_progress_done(next_step_id="select_device")

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create an entry for the chosen discovered device."""
        if user_input is not None:
            device = self._devices[user_input["device"]]
            await self.async_set_unique_id(str(device.serial))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{device.model} {device.serial}",
                data={
                    CONF_HOST: device.ip,
                    CONF_PORT: DEFAULT_PORT,
                    CONF_SERIAL: device.serial,
                    CONF_DEVICE_TYPE: device.device_type,
                },
            )

        options = [
            selector.SelectOptionDict(
                value=serial,
                label=f"{dev.model} (SN {dev.serial}) — {dev.ip}",
            )
            for serial, dev in self._devices.items()
        ]
        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual host and port entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host: str = user_input[CONF_HOST].strip()
            port: int = user_input.get(CONF_PORT, DEFAULT_PORT)
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()
            error = await _validate_connection(host, port)
            if error is None:
                return self.async_create_entry(
                    title=f"Airfi {host}",
                    data={CONF_HOST: host, CONF_PORT: port},
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="manual", data_schema=STEP_MANUAL_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AirfiOptionsFlow:
        """Return the options flow handler."""
        return AirfiOptionsFlow()


class AirfiOptionsFlow(OptionsFlow):
    """Scan interval option."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current: int = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=MIN_SCAN_INTERVAL,
                                max=MAX_SCAN_INTERVAL,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Coerce(int),
                    )
                }
            ),
        )
