"""Tests for the sensor platform.

Entity ids below are derived from the English entity names in
``custom_components/airfi/translations/en.json``, resolved via each
entity's ``_attr_translation_key`` (see task 8 report, "Fix: English
translations pulled forward"). The object id is the slugified name, e.g.
"Outdoor air temperature (T1)" -> ``outdoor_air_temperature_t1``.
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
    state = hass.states.get(
        "sensor.model_60_l_12345678_outdoor_air_temperature_t1"
    )
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
    state = hass.states.get(
        "sensor.model_60_l_12345678_outdoor_air_temperature_t1"
    )
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
    state = hass.states.get("sensor.model_60_l_12345678_supply_fan_rpm")
    assert state is not None
    assert state.state == "1450"


async def test_version_sensor_decoded(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    await _setup(
        hass, config_entry, mock_modbus_client, input_overrides={2: 214}
    )
    state = hass.states.get("sensor.model_60_l_12345678_software_version")
    assert state is not None
    assert state.state == "2.1.4"
