"""Tests for the number platform."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import make_data


async def test_setpoint_read_and_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    mock_modbus_client.read_all.return_value = make_data(
        holding_overrides={5: 215}
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "number.model_60_l_12345678_temperature_setpoint"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "21.5"
    assert state.attributes["min"] == 17.0
    assert state.attributes["max"] == 26.0

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 22.0},
        blocking=True,
    )
    mock_modbus_client.write_register.assert_awaited_with(5, 220)


async def test_write_rounding_is_decimal_exact(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    """Binary-float slop must not shift the written raw value (21.15 -> 212)."""
    mock_modbus_client.read_all.return_value = make_data(
        holding_overrides={5: 215}
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.model_60_l_12345678_temperature_setpoint",
            "value": 21.15,
        },
        blocking=True,
    )
    mock_modbus_client.write_register.assert_awaited_with(5, 212)
