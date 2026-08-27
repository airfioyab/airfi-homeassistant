"""Tests for const.py."""

from custom_components.airfi.const import DOMAIN


def test_domain() -> None:
    assert DOMAIN == "airfi"
