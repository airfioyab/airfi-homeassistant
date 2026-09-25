"""The Airfi integration."""

from __future__ import annotations

from datetime import datetime

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import CONF_DEVICE_TYPE, CONF_SERIAL, DEFAULT_PORT, DOMAIN, LOGGER
from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .discovery import AirfiDiscoveryListener, DiscoveredDevice

DISCOVERY_RETRY_DELAY = 60

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirfiConfigEntry) -> bool:
    """Unload a config entry; stop discovery when the last one unloads."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    remaining = [
        other
        for other in hass.config_entries.async_loaded_entries(DOMAIN)
        if other.entry_id != entry.entry_id
    ]
    if not remaining:
        _async_stop_discovery(hass)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: AirfiConfigEntry) -> None:
    """Handle removal of a config entry.

    HA skips async_unload_entry when a never-loaded entry (e.g. stuck in
    SETUP_RETRY because the device was unreachable) is deleted, but always
    calls this hook — without it the discovery listener started before the
    failing first refresh would leak.
    """
    if not hass.config_entries.async_entries(DOMAIN):
        _async_stop_discovery(hass)


@callback
def _async_stop_discovery(hass: HomeAssistant) -> None:
    """Stop the shared listener and any pending retry."""
    if (data := hass.data.get(DOMAIN)) is None:
        return
    # The slot may hold None while a start is still in flight; only a real
    # listener needs stopping (the starter re-checks after its await).
    listener: AirfiDiscoveryListener | None = data.pop("discovery_listener", None)
    if listener is not None:
        listener.stop()
    if (cancel_retry := data.pop("discovery_retry", None)) is not None:
        cancel_retry()


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
        _async_schedule_discovery_retry(hass)
        return
    # The last entry may have unloaded or been removed (popping our reserved
    # slot) while the start was in flight — a listener stored now would never
    # be stopped. Loaded-state cannot be checked here: during the first
    # entry's setup the listener intentionally starts before the entry is
    # LOADED, so the popped slot is the only reliable signal.
    if "discovery_listener" not in data:
        listener.stop()
        return
    data["discovery_listener"] = listener
    # A retry may still be pending if this start was itself a retry attempt
    # racing a concurrent one, or if the caller is the leader after a prior
    # failure; either way a running listener means it is no longer needed.
    if (cancel_retry := data.pop("discovery_retry", None)) is not None:
        cancel_retry()


@callback
def _async_schedule_discovery_retry(hass: HomeAssistant) -> None:
    """Schedule a single retry of the discovery listener after a failure.

    Without this, a leader whose start fails leaves every loaded entry
    stranded: the slot is popped so nothing looks "in flight", but no
    loaded entry ever calls back in to retry until one of them reloads.
    """
    data = hass.data.setdefault(DOMAIN, {})
    if (cancel_retry := data.pop("discovery_retry", None)) is not None:
        cancel_retry()

    async def _retry(_now: datetime) -> None:
        hass.data.get(DOMAIN, {}).pop("discovery_retry", None)
        if hass.config_entries.async_loaded_entries(DOMAIN):
            await _async_ensure_discovery_listener(hass)

    data["discovery_retry"] = async_call_later(hass, DISCOVERY_RETRY_DELAY, _retry)


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
                hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_HOST: device.ip}
                )
                hass.config_entries.async_schedule_reload(entry.entry_id)
            return
    # No serial match: upgrade a manual entry for this host. Announcing
    # devices always serve Modbus on the default port, so a manual entry on
    # another port is a different endpoint and must not adopt this identity.
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data.get(CONF_HOST) == device.ip
            and entry.data.get(CONF_PORT, DEFAULT_PORT) == DEFAULT_PORT
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
            hass.config_entries.async_schedule_reload(entry.entry_id)
            return
