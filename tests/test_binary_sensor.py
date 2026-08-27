"""Tests for the binary sensor platform.

See tests/test_sensor.py's module docstring for why entity ids here are
generic slugs rather than per-key names: with no strings.json yet, HA never
reaches translation_key-based naming for these platforms, so device-class
binary sensors collide onto one generic name each ("Problem", "Running", ...)
and non-device-class ones (like fireplace_active) get no name at all.
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

    # fireplace_active (address 15): no device class, first nameless binary
    # sensor in BINARY_SENSOR_REGISTERS order, so it gets the bare device slug.
    assert hass.states.get("binary_sensor.model_60_l_12345678").state == "on"
    # error_e0/e1/e2 (address 32, bits 0-2): all device_class PROBLEM, so all
    # collide onto the generic "Problem" name; these are the 6th-8th such
    # entities registered (after emergency_stop, machine_fault,
    # constant_pressure_supply_alarm, constant_pressure_exhaust_alarm,
    # filter_guard_alarm).
    assert (
        hass.states.get("binary_sensor.model_60_l_12345678_problem_6").state == "on"
    )
    assert (
        hass.states.get("binary_sensor.model_60_l_12345678_problem_7").state == "off"
    )
    assert (
        hass.states.get("binary_sensor.model_60_l_12345678_problem_8").state == "on"
    )
