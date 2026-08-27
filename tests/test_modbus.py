"""Tests for the Modbus client wrapper (pymodbus mocked)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.airfi.modbus import (
    AirfiConnectionError,
    AirfiModbusClient,
    AirfiModbusError,
)


def _read_result(values: list[int]) -> MagicMock:
    result = MagicMock()
    result.isError.return_value = False
    result.registers = values
    return result


@pytest.fixture
def mock_pymodbus() -> AsyncMock:
    with patch(
        "custom_components.airfi.modbus.AsyncModbusTcpClient", autospec=True
    ) as client_cls:
        client = client_cls.return_value
        client.connect = AsyncMock(return_value=True)
        client.close = MagicMock()
        client.read_input_registers = AsyncMock(
            side_effect=lambda address, count: _read_result(list(range(count)))
        )
        client.read_holding_registers = AsyncMock(
            side_effect=lambda address, count: _read_result(list(range(count)))
        )
        client.write_register = AsyncMock(return_value=_read_result([]))
        yield client


async def test_read_all_batches_and_addressing(mock_pymodbus: AsyncMock) -> None:
    client = AirfiModbusClient("1.2.3.4", 502)
    data = await client.read_all()

    # 1-based spec addresses become 0-based wire addresses.
    input_calls = [c.kwargs for c in mock_pymodbus.read_input_registers.call_args_list]
    assert input_calls == [
        {"address": 0, "count": 20},
        {"address": 20, "count": 20},
        {"address": 40, "count": 9},
    ]
    holding_calls = [
        c.kwargs for c in mock_pymodbus.read_holding_registers.call_args_list
    ]
    assert holding_calls == [
        {"address": 0, "count": 20},
        {"address": 20, "count": 20},
        {"address": 40, "count": 20},
        {"address": 60, "count": 8},
    ]
    # Results are keyed by 1-based address.
    assert data["input"][1] == 0
    assert data["input"][21] == 0
    assert data["input"][49] == 8
    assert set(data["holding"]) == set(range(1, 69))
    # Connection is closed after the operation.
    mock_pymodbus.close.assert_called()


async def test_read_all_connection_refused(mock_pymodbus: AsyncMock) -> None:
    mock_pymodbus.connect.return_value = False
    client = AirfiModbusClient("1.2.3.4", 502)
    with pytest.raises(AirfiConnectionError):
        await client.read_all()


async def test_read_all_modbus_error(mock_pymodbus: AsyncMock) -> None:
    bad = MagicMock()
    bad.isError.return_value = True
    mock_pymodbus.read_input_registers = AsyncMock(return_value=bad)
    client = AirfiModbusClient("1.2.3.4", 502)
    with pytest.raises(AirfiModbusError):
        await client.read_all()
    mock_pymodbus.close.assert_called()


async def test_write_register(mock_pymodbus: AsyncMock) -> None:
    client = AirfiModbusClient("1.2.3.4", 502)
    await client.write_register(5, 215)
    mock_pymodbus.write_register.assert_awaited_once_with(address=4, value=215)
    mock_pymodbus.close.assert_called()


async def test_validation_read(mock_pymodbus: AsyncMock) -> None:
    mock_pymodbus.read_input_registers = AsyncMock(return_value=_read_result([7]))
    client = AirfiModbusClient("1.2.3.4", 502)
    assert await client.read_input_register(1) == 7
    mock_pymodbus.read_input_registers.assert_awaited_once_with(address=0, count=1)
