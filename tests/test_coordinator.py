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


async def test_register_version_mismatch_warns_once(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unexpected register-layout version logs one warning, non-fatal."""
    mock_modbus_client.read_all.return_value = make_data(
        input_overrides={3: 999}
    )
    config_entry.add_to_hass(hass)
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert caplog.text.count("Modbus register version 999") == 1


async def test_input_extension_gated_by_register_version(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    """Registers 50-52 are read only when the firmware version has them."""
    mock_modbus_client.read_all.return_value = make_data(
        input_overrides={3: 360}
    )
    mock_modbus_client.read_input_batch.return_value = {50: 650, 51: 120, 52: 115}
    config_entry.add_to_hass(hass)
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    mock_modbus_client.read_input_batch.assert_awaited_once_with(50, 3)
    assert coordinator.data["input"][51] == 120
    # Subsequent polls pass the extension straight into read_all.
    await coordinator.async_refresh()
    mock_modbus_client.read_all.assert_awaited_with((50, 3))


async def test_no_input_extension_on_old_firmware(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    mock_modbus_client.read_all.return_value = make_data(
        input_overrides={3: 330}
    )
    config_entry.add_to_hass(hass)
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    mock_modbus_client.read_input_batch.assert_not_awaited()
    await coordinator.async_refresh()
    mock_modbus_client.read_all.assert_awaited_with(None)
