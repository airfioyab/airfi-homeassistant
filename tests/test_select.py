"""Tests for the select platform.

Entity ids below are derived from the English entity names in
``custom_components/airfi/translations/en.json``, resolved via each
entity's ``_attr_translation_key`` (see task 8 report, "Fix: English
translations pulled forward"). The "speed" register's English name is
"Fan speed", so its object id is ``fan_speed``, not ``speed``.
"""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import make_data


async def test_speed_select_read_and_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    mock_modbus_client.read_all.return_value = make_data(holding_overrides={1: 3})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "select.model_60_l_12345678_fan_speed"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "speed_3"
    assert state.attributes["options"] == [
        "off",
        "speed_1",
        "speed_2",
        "speed_3",
        "speed_4",
        "speed_5",
    ]

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "speed_5"},
        blocking=True,
    )
    mock_modbus_client.write_register.assert_awaited_with(1, 5)
