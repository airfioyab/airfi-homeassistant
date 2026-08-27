"""Consistency tests for the register descriptor tables."""

from custom_components.airfi.const import REG_HOLDING, REG_INPUT
from custom_components.airfi.registers import (
    BINARY_SENSOR_REGISTERS,
    NUMBER_REGISTERS,
    SELECT_REGISTERS,
    SENSOR_REGISTERS,
    SWITCH_REGISTERS,
    scaled_value,
)


def test_input_register_coverage() -> None:
    """All input registers except unused 10 and reserved 20 are exposed."""
    addresses = {r.address for r in SENSOR_REGISTERS if r.register_type == REG_INPUT}
    addresses |= {
        r.address for r in BINARY_SENSOR_REGISTERS if r.register_type == REG_INPUT
    }
    assert addresses == set(range(1, 50)) - {10, 20}


def test_holding_register_coverage() -> None:
    """Every holding register 1–68 is exposed by exactly one writable platform."""
    numbers = [r.address for r in NUMBER_REGISTERS]
    selects = [r.address for r in SELECT_REGISTERS]
    switches = [r.address for r in SWITCH_REGISTERS]
    combined = numbers + selects + switches
    assert sorted(combined) == list(range(1, 69))


def test_keys_unique_per_platform() -> None:
    for table in (
        SENSOR_REGISTERS,
        NUMBER_REGISTERS,
        SELECT_REGISTERS,
        SWITCH_REGISTERS,
    ):
        keys = [r.key for r in table]
        assert len(keys) == len(set(keys))
    # Binary sensors: (key) unique; register 32 repeats with distinct bits.
    bin_keys = [r.key for r in BINARY_SENSOR_REGISTERS]
    assert len(bin_keys) == len(set(bin_keys))


def test_select_options_within_spec_range() -> None:
    speed = next(r for r in SELECT_REGISTERS if r.key == "speed")
    assert [raw for raw, _ in speed.options] == [0, 1, 2, 3, 4, 5]


def test_temperature_sensors_are_signed() -> None:
    outdoor = next(r for r in SENSOR_REGISTERS if r.address == 4)
    assert outdoor.signed is True
    assert outdoor.scale == 0.1


def test_scaled_value() -> None:
    assert scaled_value(215, 0.1) == 21.5
    assert scaled_value(0xFFCE, 0.1, signed=True) == -5.0  # -50 raw
    assert scaled_value(3, 1.0) == 3
