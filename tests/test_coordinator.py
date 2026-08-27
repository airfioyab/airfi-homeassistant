"""Tests for the Airfi coordinator."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airfi.const import DOMAIN, REG_HOLDING
from custom_components.airfi.coordinator import AirfiCoordinator
from custom_components.airfi.modbus import AirfiConnectionError

from .conftest import make_data


async def test_update_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    mock_modbus_client.read_all.return_value = make_data(input_overrides={4: 215})
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data["input"][4] == 215


async def test_update_failure_wraps_client_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    mock_modbus_client.read_all.side_effect = AirfiConnectionError("nope")
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    assert not coordinator.last_update_success


async def test_device_info(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    mock_modbus_client.read_all.return_value = make_data(
        input_overrides={1: 100, 2: 214}
    )
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    info = coordinator.device_info
    assert info["identifiers"] == {(DOMAIN, config_entry.entry_id)}
    assert info["manufacturer"] == "Airfi"
    assert info["model"] == "Model 60 L"
    assert info["hw_version"] == "1.0.0"
    assert info["sw_version"] == "2.1.4"


async def test_write_value_updates_cache_and_refreshes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    await coordinator.async_write_value(5, 215)
    mock_modbus_client.write_register.assert_awaited_once_with(5, 215)
    assert coordinator.data[REG_HOLDING][5] == 215
    # async_write_value's async_request_refresh() leaves the coordinator's
    # request-refresh debouncer holding a cooldown timer (HA only cancels it
    # via config entry unload, which this test never triggers); shut it down
    # explicitly so pytest-homeassistant's lingering-timer check stays clean.
    await coordinator.async_shutdown()


async def test_write_failure_raises_homeassistant_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    from homeassistant.exceptions import HomeAssistantError

    config_entry.add_to_hass(hass)
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    mock_modbus_client.write_register.side_effect = AirfiConnectionError("nope")
    with pytest.raises(HomeAssistantError):
        await coordinator.async_write_value(5, 215)
