"""Locked, connect-per-operation Modbus TCP client for Airfi devices.

The device allows only one Modbus client at a time and at most 20 registers
per read. Both constraints are handled here so nothing else has to care.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    DEFAULT_MODBUS_ID,
    HOLDING_REGISTER_BATCHES,
    INPUT_REGISTER_BATCHES,
    MODBUS_TIMEOUT,
    REG_HOLDING,
    REG_INPUT,
)

type AirfiData = dict[str, dict[int, int]]


class AirfiConnectionError(Exception):
    """Could not connect to the device."""


class AirfiModbusError(Exception):
    """The device rejected a request or the transfer failed."""


class AirfiModbusClient:
    """Connects per operation; serializes all access with a lock."""

    def __init__(
        self, host: str, port: int, device_id: int = DEFAULT_MODBUS_ID
    ) -> None:
        self._host = host
        self._port = port
        self._device_id = device_id
        self._lock = asyncio.Lock()
        self._client = AsyncModbusTcpClient(
            host=host, port=port, timeout=MODBUS_TIMEOUT
        )

    async def _connect(self) -> None:
        try:
            connected = await self._client.connect()
        except (OSError, TimeoutError, ModbusException) as err:
            self._client.close()
            raise AirfiConnectionError(
                f"Cannot connect to Airfi device at {self._host}:{self._port}: {err}"
            ) from err
        if not connected:
            self._client.close()
            raise AirfiConnectionError(
                f"Cannot connect to Airfi device at {self._host}:{self._port}"
            )

    async def _read_batch(
        self,
        read: Callable[..., Awaitable[Any]],
        start: int,
        count: int,
    ) -> dict[int, int]:
        """Read one batch; returns {1-based address: raw value}.

        The Airfi firmware deviates from the Modbus convention: the wire
        address IS the 1-based register number (verified against
        modbus-handler.cpp; address 0 is rejected as IllegalDataAddress).
        """
        result = await read(
            address=start, count=count, device_id=self._device_id
        )
        if result.isError():
            raise AirfiModbusError(
                f"Modbus error reading registers {start}-{start + count - 1}: {result}"
            )
        return {start + i: value for i, value in enumerate(result.registers)}

    async def read_all(
        self, extra_input_batch: tuple[int, int] | None = None
    ) -> AirfiData:
        """Read every defined register, plus an optional extension batch."""
        async with self._lock:
            await self._connect()
            try:
                data: AirfiData = {REG_INPUT: {}, REG_HOLDING: {}}
                input_batches = list(INPUT_REGISTER_BATCHES)
                if extra_input_batch is not None:
                    input_batches.append(extra_input_batch)
                for start, count in input_batches:
                    data[REG_INPUT].update(
                        await self._read_batch(
                            self._client.read_input_registers, start, count
                        )
                    )
                for start, count in HOLDING_REGISTER_BATCHES:
                    data[REG_HOLDING].update(
                        await self._read_batch(
                            self._client.read_holding_registers, start, count
                        )
                    )
                return data
            except ModbusException as err:
                raise AirfiModbusError(f"Modbus communication error: {err}") from err
            finally:
                self._client.close()

    async def read_holding_batch(self, start: int, count: int) -> dict[int, int]:
        """Read one holding-register batch (1-based start, count <= 20)."""
        async with self._lock:
            await self._connect()
            try:
                return await self._read_batch(
                    self._client.read_holding_registers, start, count
                )
            except ModbusException as err:
                raise AirfiModbusError(f"Modbus communication error: {err}") from err
            finally:
                self._client.close()

    async def read_input_batch(self, start: int, count: int) -> dict[int, int]:
        """Read one input-register batch (1-based start, count <= 20)."""
        async with self._lock:
            await self._connect()
            try:
                return await self._read_batch(
                    self._client.read_input_registers, start, count
                )
            except ModbusException as err:
                raise AirfiModbusError(f"Modbus communication error: {err}") from err
            finally:
                self._client.close()

    async def read_input_register(self, address: int) -> int:
        """Read a single input register (1-based); used for validation."""
        async with self._lock:
            await self._connect()
            try:
                batch = await self._read_batch(
                    self._client.read_input_registers, address, 1
                )
                return batch[address]
            except ModbusException as err:
                raise AirfiModbusError(f"Modbus communication error: {err}") from err
            finally:
                self._client.close()

    async def write_register(self, address: int, value: int) -> None:
        """Write a single holding register (1-based)."""
        async with self._lock:
            await self._connect()
            try:
                result = await self._client.write_register(
                    address=address, value=value, device_id=self._device_id
                )
                if result.isError():
                    raise AirfiModbusError(
                        f"Device rejected write of {value} to register {address}: "
                        f"{result}"
                    )
            except ModbusException as err:
                raise AirfiModbusError(f"Modbus communication error: {err}") from err
            finally:
                self._client.close()
