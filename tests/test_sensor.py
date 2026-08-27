"""Tests for the sensor platform.

Entity ids below are pinned to actual HA behavior, not to the register key:
with no strings.json yet, HA's ``Entity.name`` resolution never reaches the
translation_key at all (that lookup only fires through an EntityDescription,
which these platforms don't use). Sensors with a device_class instead get
named generically from HA's own device-class translations (e.g. "Temperature"
for every temperature sensor), and sensors without a device_class get no name.
Either way, the object id falls back to a shared/generic slug with numeric
suffixes assigned in SENSOR_REGISTERS order. This will become the readable
per-key id once entity name translations are added (see task 8 report).
"""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import make_data


async def _setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
    **overrides: dict[int, int],
) -> None:
    mock_modbus_client.read_all.return_value = make_data(**overrides)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_temperature_sensor_scaling(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    await _setup(
        hass, config_entry, mock_modbus_client, input_overrides={4: 215}
    )
    # outdoor_air_temperature (address 4): first temperature-class sensor
    # registered, so it gets the bare generic object id (see module docstring).
    state = hass.states.get("sensor.model_60_l_12345678_temperature")
    assert state is not None
    assert state.state == "21.5"
    assert state.attributes["unit_of_measurement"] == "°C"


async def test_negative_temperature(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    await _setup(
        hass, config_entry, mock_modbus_client, input_overrides={4: 0xFFCE}
    )
    state = hass.states.get("sensor.model_60_l_12345678_temperature")
    assert state is not None
    assert state.state == "-5.0"


async def test_unscaled_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    await _setup(
        hass, config_entry, mock_modbus_client, input_overrides={21: 1450}
    )
    # supply_fan_rpm (address 21): no device class, so HA assigns it no name
    # at all; it is the 6th such nameless sensor in SENSOR_REGISTERS order.
    state = hass.states.get("sensor.model_60_l_12345678_6")
    assert state is not None
    assert state.state == "1450"
