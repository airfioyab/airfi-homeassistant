"""Data update coordinator for one Airfi device."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DEVICE_TYPE,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    REG_HOLDING,
    REG_INPUT,
    model_name,
)
from .modbus import (
    AirfiConnectionError,
    AirfiData,
    AirfiModbusClient,
    AirfiModbusError,
)

type AirfiConfigEntry = ConfigEntry[AirfiCoordinator]


class AirfiCoordinator(DataUpdateCoordinator[AirfiData]):
    """Polls all registers of one Airfi device."""

    config_entry: AirfiConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: AirfiConfigEntry) -> None:
        """Initialize with connection parameters from the config entry."""
        scan_interval: int = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"Airfi {config_entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = AirfiModbusClient(
            config_entry.data[CONF_HOST], config_entry.data[CONF_PORT]
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Device registry entry shared by all this device's entities."""
        hw_version: int | None = None
        sw_version: int | None = None
        if self.data:
            hw_version = self.data[REG_INPUT].get(1)
            sw_version = self.data[REG_INPUT].get(2)
        device_type = self.config_entry.data.get(CONF_DEVICE_TYPE)
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.config_entry.unique_id or self.config_entry.entry_id)
            },
            name=self.config_entry.title,
            manufacturer="Airfi",
            model=model_name(device_type) if device_type is not None else None,
            hw_version=str(hw_version) if hw_version is not None else None,
            sw_version=str(sw_version) if sw_version is not None else None,
            configuration_url=f"http://{self.config_entry.data[CONF_HOST]}",
        )

    async def _async_update_data(self) -> AirfiData:
        """Read all registers from the device."""
        try:
            return await self.client.read_all()
        except (AirfiConnectionError, AirfiModbusError) as err:
            raise UpdateFailed(str(err)) from err

    async def async_write_value(self, address: int, raw_value: int) -> None:
        """Write one holding register, update the cache, and refresh."""
        try:
            await self.client.write_register(address, raw_value)
        except (AirfiConnectionError, AirfiModbusError) as err:
            raise HomeAssistantError(
                f"Writing register {address} failed: {err}"
            ) from err
        if self.data is not None:
            self.data[REG_HOLDING][address] = raw_value
            self.async_update_listeners()
        await self.async_request_refresh()
