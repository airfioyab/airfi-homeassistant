"""Shared fixtures for the Airfi integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airfi.const import (
    CONF_DEVICE_TYPE,
    CONF_SERIAL,
    DOMAIN,
    REG_HOLDING,
    REG_INPUT,
)
from custom_components.airfi.modbus import AirfiData


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture(autouse=True)
def mock_discovery_listener() -> Generator[AsyncMock]:
    """Prevent real multicast sockets in tests; capture the callback."""
    with patch(
        "custom_components.airfi.AirfiDiscoveryListener", autospec=True
    ) as listener_cls:
        yield listener_cls


def make_data(
    input_overrides: dict[int, int] | None = None,
    holding_overrides: dict[int, int] | None = None,
) -> AirfiData:
    """Full register data set, zeros except for the given overrides."""
    data: AirfiData = {
        REG_INPUT: dict.fromkeys(range(1, 50), 0),
        REG_HOLDING: dict.fromkeys(range(1, 69), 0),
    }
    data[REG_INPUT].update(input_overrides or {})
    data[REG_HOLDING].update(holding_overrides or {})
    return data


@pytest.fixture
def mock_modbus_client() -> Generator[AsyncMock]:
    """Mock AirfiModbusClient wherever the integration constructs it."""
    with patch(
        "custom_components.airfi.coordinator.AirfiModbusClient", autospec=True
    ) as client_cls:
        client = client_cls.return_value
        client.read_all = AsyncMock(return_value=make_data())
        client.write_register = AsyncMock()
        client.read_holding_batch = AsyncMock(return_value={})
        client.read_input_register = AsyncMock(return_value=1)
        yield client


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Model 60 L 12345678",
        unique_id="12345678",
        data={
            "host": "192.168.1.50",
            "port": 502,
            CONF_SERIAL: 12345678,
            CONF_DEVICE_TYPE: 1,
        },
    )
