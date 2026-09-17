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
    EXPECTED_MODBUS_REGISTER_VERSION,
    HOLDING_REGISTER_BATCHES,
    INPUT_EXTENSION_BATCHES,
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
from .registers import format_version

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
        self._version_checked = False
        # Chosen after the first read based on the device's reported
        # register version; None until then (and for old firmware).
        self._input_extension: tuple[int, int] | None = None

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
            # The config-entry unique_id is reserved for duplicate detection
            # and may change (manual->serial upgrade); registry identity must
            # use the immutable entry_id.
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name=self.config_entry.title,
            manufacturer="Airfi",
            model=model_name(device_type) if device_type is not None else None,
            hw_version=format_version(hw_version) if hw_version is not None else None,
            sw_version=format_version(sw_version) if sw_version is not None else None,
            configuration_url=f"http://{self.config_entry.data[CONF_HOST]}",
        )

    async def _async_update_data(self) -> AirfiData:
        """Read all registers from the device."""
        try:
            data = await self.client.read_all(self._input_extension)
        except (AirfiConnectionError, AirfiModbusError) as err:
            raise UpdateFailed(str(err)) from err
        if not self._version_checked:
            self._version_checked = True
            reported = data[REG_INPUT].get(3)
            if reported is not None and reported != EXPECTED_MODBUS_REGISTER_VERSION:
                LOGGER.warning(
                    (
                        "Device %s reports Modbus register version %s; this "
                        "integration was built against %s — some values may "
                        "be mapped incorrectly"
                    ),
                    self.config_entry.title,
                    reported,
                    EXPECTED_MODBUS_REGISTER_VERSION,
                )
            # Registers beyond 49 exist only on newer register versions;
            # reading them on older firmware would fail the whole batch.
            if reported is not None:
                for min_version, batch in INPUT_EXTENSION_BATCHES:
                    if reported >= min_version:
                        self._input_extension = batch
                        break
            if self._input_extension is not None:
                try:
                    data[REG_INPUT].update(
                        await self.client.read_input_batch(*self._input_extension)
                    )
                except (AirfiConnectionError, AirfiModbusError) as err:
                    LOGGER.debug("Extension batch read failed: %s", err)
        return data

    async def async_write_value(self, address: int, raw_value: int) -> None:
        """Write one holding register and confirm it from the device.

        Only the holding batch containing the register is re-read (a full
        read_all per write would cost 7 extra transactions); any knock-on
        effects in other registers arrive with the next scheduled poll.
        """
        try:
            await self.client.write_register(address, raw_value)
        except (AirfiConnectionError, AirfiModbusError) as err:
            raise HomeAssistantError(
                f"Writing register {address} failed: {err}"
            ) from err
        if self.data is None:
            await self.async_request_refresh()
            return
        self.data[REG_HOLDING][address] = raw_value
        try:
            for start, count in HOLDING_REGISTER_BATCHES:
                if start <= address < start + count:
                    self.data[REG_HOLDING].update(
                        await self.client.read_holding_batch(start, count)
                    )
                    break
        except (AirfiConnectionError, AirfiModbusError) as err:
            # The write itself succeeded; keep the optimistic value and let
            # the next scheduled poll reconcile.
            LOGGER.debug("Post-write confirmation read failed: %s", err)
        self.async_update_listeners()
