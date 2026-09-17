"""Tests for the button platform."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import make_data


async def test_filter_reminder_state_and_reset(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    """Register 34: reads reminder state; the button writes 0 to clear it."""
    mock_modbus_client.read_all.return_value = make_data(
        holding_overrides={34: 1}
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(
        "binary_sensor.model_60_l_12345678_filter_change_due"
    )
    assert state is not None
    assert state.state == "on"
    assert "device_class" not in state.attributes

    await hass.services.async_call(
        "button",
        "press",
        {
            "entity_id": (
                "button.model_60_l_12345678_reset_filter_change_reminder"
            )
        },
        blocking=True,
    )
    mock_modbus_client.write_register.assert_awaited_with(34, 0)
