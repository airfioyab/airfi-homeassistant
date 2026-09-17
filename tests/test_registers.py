"""Consistency tests for the register descriptor tables."""

from custom_components.airfi.const import (
    HOLDING_REGISTER_BATCHES,
    INPUT_EXTENSION_BATCHES,
    INPUT_REGISTER_BATCHES,
    REG_INPUT,
)
from custom_components.airfi.registers import (
    BINARY_SENSOR_REGISTERS,
    BUTTON_REGISTERS,
    NUMBER_REGISTERS,
    SELECT_REGISTERS,
    SENSOR_REGISTERS,
    SWITCH_REGISTERS,
    format_version,
    scaled_value,
)


def test_input_register_coverage() -> None:
    """All input registers except unused 10 and reserved 20 are exposed."""
    addresses = {r.address for r in SENSOR_REGISTERS if r.register_type == REG_INPUT}
    addresses |= {
        r.address for r in BINARY_SENSOR_REGISTERS if r.register_type == REG_INPUT
    }
    assert addresses == set(range(1, 53)) - {10, 20}


def test_holding_register_coverage() -> None:
    """Every holding register 1–68 is exposed by exactly one writable platform."""
    numbers = [r.address for r in NUMBER_REGISTERS]
    selects = [r.address for r in SELECT_REGISTERS]
    switches = [r.address for r in SWITCH_REGISTERS]
    buttons = [r.address for r in BUTTON_REGISTERS]
    combined = numbers + selects + switches + buttons
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


def test_format_version() -> None:
    """Firmware packs versions as major*100 + minor*10 + patch."""
    assert format_version(123) == "1.2.3"
    assert format_version(100) == "1.0.0"
    assert format_version(3) == "0.0.3"
    assert format_version(1205) == "12.0.5"


def test_version_sensors_marked_and_not_statistics() -> None:
    for address, is_version in ((1, True), (2, True), (3, False)):
        desc = next(r for r in SENSOR_REGISTERS if r.address == address)
        assert desc.is_version is is_version
        assert desc.state_class is None


def test_every_descriptor_address_is_polled() -> None:
    """The batch lists must cover every register the tables expose.

    A register outside every batch is silently never fetched and its
    entity stays unknown forever.
    """
    input_covered: set[int] = set()
    for start, count in INPUT_REGISTER_BATCHES:
        input_covered.update(range(start, start + count))
    for _min_version, (start, count) in INPUT_EXTENSION_BATCHES:
        input_covered.update(range(start, start + count))
    holding_covered: set[int] = set()
    for start, count in HOLDING_REGISTER_BATCHES:
        holding_covered.update(range(start, start + count))

    input_addresses = {r.address for r in SENSOR_REGISTERS} | {
        r.address for r in BINARY_SENSOR_REGISTERS
    }
    holding_addresses = (
        {r.address for r in NUMBER_REGISTERS}
        | {r.address for r in SELECT_REGISTERS}
        | {r.address for r in SWITCH_REGISTERS}
        | {r.address for r in BUTTON_REGISTERS}
    )
    assert input_addresses <= input_covered
    assert holding_addresses <= holding_covered
