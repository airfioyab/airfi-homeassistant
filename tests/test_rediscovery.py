"""Tests for automatic host updates from announcements."""

from collections.abc import Callable
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airfi.const import CONF_DEVICE_TYPE, CONF_SERIAL, DOMAIN
from custom_components.airfi.discovery import DiscoveredDevice


def _get_callback(
    mock_discovery_listener: AsyncMock,
) -> Callable[[DiscoveredDevice], None]:
    return mock_discovery_listener.call_args.args[0]


async def test_host_update_on_new_ip(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
    mock_discovery_listener: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    on_device = _get_callback(mock_discovery_listener)
    on_device(
        DiscoveredDevice(
            ip="192.168.1.99",
            udp_port=4000,
            serial=12345678,
            protocol_version=1,
            device_type=1,
        )
    )
    await hass.async_block_till_done()
    assert config_entry.data["host"] == "192.168.1.99"


async def test_manual_entry_upgraded_with_serial(
    hass: HomeAssistant,
    mock_modbus_client: AsyncMock,
    mock_discovery_listener: AsyncMock,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Airfi 192.168.1.50",
        unique_id="192.168.1.50:502",
        data={"host": "192.168.1.50", "port": 502},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    on_device = _get_callback(mock_discovery_listener)
    on_device(
        DiscoveredDevice(
            ip="192.168.1.50",
            udp_port=4000,
            serial=87654321,
            protocol_version=1,
            device_type=3,
        )
    )
    await hass.async_block_till_done()
    assert entry.unique_id == "87654321"
    assert entry.data[CONF_SERIAL] == 87654321
    assert entry.data[CONF_DEVICE_TYPE] == 3
