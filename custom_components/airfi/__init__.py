"""The Airfi integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback

from .const import CONF_DEVICE_TYPE, CONF_SERIAL, DOMAIN, LOGGER
from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .discovery import AirfiDiscoveryListener, DiscoveredDevice

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: AirfiConfigEntry) -> bool:
    """Set up an Airfi device from a config entry."""
    # Start the announcement listener before the first refresh: if the device
    # moved to a new IP the refresh fails, but an announcement can then heal
    # the entry's host while HA retries the setup.
    await _async_ensure_discovery_listener(hass)

    coordinator = AirfiCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: AirfiConfigEntry) -> None:
    """Reload the entry when options (scan interval) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AirfiConfigEntry) -> bool:
    """Unload a config entry; stop discovery when the last one unloads."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    remaining = [
        other
        for other in hass.config_entries.async_loaded_entries(DOMAIN)
        if other.entry_id != entry.entry_id
    ]
    if not remaining and (data := hass.data.get(DOMAIN)):
        # The slot may hold None while a start is still in flight; only a
        # real listener needs stopping.
        listener: AirfiDiscoveryListener | None = data.pop(
            "discovery_listener", None
        )
        if listener is not None:
            listener.stop()
    return unloaded


async def _async_ensure_discovery_listener(hass: HomeAssistant) -> None:
    """Start the shared announcement listener once."""
    data = hass.data.setdefault(DOMAIN, {})
    if "discovery_listener" in data:
        return
    # Reserve the slot before the first await so a second entry setting up
    # concurrently cannot also pass the check and start a second listener.
    data["discovery_listener"] = None

    @callback
    def _on_device(device: DiscoveredDevice) -> None:
        _async_handle_announcement(hass, device)

    listener = AirfiDiscoveryListener(_on_device)
    try:
        await listener.async_start()
    except OSError as err:
        data.pop("discovery_listener", None)
        LOGGER.warning("Rediscovery listener could not start: %s", err)
        return
    data["discovery_listener"] = listener


@callback
def _async_handle_announcement(hass: HomeAssistant, device: DiscoveredDevice) -> None:
    """Update configured entries from a received announcement."""
    serial_id = str(device.serial)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == serial_id:
            if entry.data.get(CONF_HOST) != device.ip:
                LOGGER.info(
                    "Airfi %s moved to %s; updating", serial_id, device.ip
                )
                # async_update_entry fires the entry's update listeners, which
                # reload the entry; no explicit reload is needed here.
                hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_HOST: device.ip}
                )
            return
    # No serial match: upgrade a manual entry for this host.
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data.get(CONF_HOST) == device.ip
            and entry.data.get(CONF_SERIAL) is None
        ):
            LOGGER.info(
                "Upgrading manual entry %s with serial %s", device.ip, serial_id
            )
            hass.config_entries.async_update_entry(
                entry,
                unique_id=serial_id,
                data={
                    **entry.data,
                    CONF_SERIAL: device.serial,
                    CONF_DEVICE_TYPE: device.device_type,
                },
            )
            return
