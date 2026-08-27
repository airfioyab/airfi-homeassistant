"""Tests for the binary sensor platform.

See tests/test_sensor.py's module docstring: entity ids here are derived
from the English entity names in
``custom_components/airfi/translations/en.json``.
"""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import make_data


async def test_plain_and_bitmask_binary_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    mock_modbus_client.read_all.return_value = make_data(
        input_overrides={15: 1, 32: 0b101}  # fireplace on; errors E0 and E2 set
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # fireplace_active (address 15): "Fireplace mode active"
    assert (
        hass.states.get(
            "binary_sensor.model_60_l_12345678_fireplace_mode_active"
        ).state
        == "on"
    )
    # error_e0/e1/e2 (address 32, bits 0-2): "Error E0"/"Error E1"/"Error E2"
    assert (
        hass.states.get("binary_sensor.model_60_l_12345678_error_e0").state == "on"
    )
    assert (
        hass.states.get("binary_sensor.model_60_l_12345678_error_e1").state == "off"
    )
    assert (
        hass.states.get("binary_sensor.model_60_l_12345678_error_e2").state == "on"
    )
