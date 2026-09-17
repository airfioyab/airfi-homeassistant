"""Every register key must have a translated name in every language."""

import json
import pathlib

import pytest

from custom_components.airfi.registers import (
    BINARY_SENSOR_REGISTERS,
    BUTTON_REGISTERS,
    NUMBER_REGISTERS,
    SELECT_REGISTERS,
    SENSOR_REGISTERS,
    SWITCH_REGISTERS,
)

TRANSLATIONS = pathlib.Path("custom_components/airfi/translations")

PLATFORM_TABLES = {
    "sensor": SENSOR_REGISTERS,
    "binary_sensor": BINARY_SENSOR_REGISTERS,
    "number": NUMBER_REGISTERS,
    "select": SELECT_REGISTERS,
    "switch": SWITCH_REGISTERS,
    "button": BUTTON_REGISTERS,
}


@pytest.mark.parametrize("language", ["en", "fi", "sv"])
def test_all_register_keys_translated(language: str) -> None:
    data = json.loads((TRANSLATIONS / f"{language}.json").read_text())
    entities = data["entity"]
    for platform, table in PLATFORM_TABLES.items():
        translated = entities[platform]
        for register in table:
            assert register.key in translated, (
                f"{language}: missing {platform}.{register.key}"
            )
            assert translated[register.key]["name"]


@pytest.mark.parametrize("language", ["en", "fi", "sv"])
def test_select_options_translated(language: str) -> None:
    data = json.loads((TRANSLATIONS / f"{language}.json").read_text())
    selects = data["entity"]["select"]
    for register in SELECT_REGISTERS:
        state = selects[register.key]["state"]
        for _, option in register.options:
            assert option in state, (
                f"{language}: missing option {register.key}.{option}"
            )
