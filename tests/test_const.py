"""Tests for const.py."""

from custom_components.airfi.const import (
    DOMAIN,
    HOLDING_REGISTER_BATCHES,
    INPUT_REGISTER_BATCHES,
    MAX_REGISTERS_PER_READ,
    model_name,
)


def test_domain() -> None:
    assert DOMAIN == "airfi"


def test_batches_respect_device_limit() -> None:
    for start, count in INPUT_REGISTER_BATCHES + HOLDING_REGISTER_BATCHES:
        assert 1 <= count <= MAX_REGISTERS_PER_READ
        assert start >= 1


def test_batches_cover_registers_contiguously() -> None:
    covered_input: set[int] = set()
    for start, count in INPUT_REGISTER_BATCHES:
        covered_input.update(range(start, start + count))
    assert covered_input == set(range(1, 50))

    covered_holding: set[int] = set()
    for start, count in HOLDING_REGISTER_BATCHES:
        covered_holding.update(range(start, start + count))
    assert covered_holding == set(range(1, 69))


def test_model_name() -> None:
    assert model_name(1) == "Model 60 L"
    assert model_name(20) == "Model C5 R Water"
    assert model_name(38) == "Model 350 Ent R Water"
    assert model_name(999) == "Airfi unit (type 999)"
