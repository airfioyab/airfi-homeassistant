"""Tests for the simulator's Modbus request handling."""

import struct

from tools.simulator import RegisterStore, build_response


def _request(function: int, address: int, value_or_count: int) -> bytes:
    # MBAP: transaction 1, protocol 0, length 6, unit 1 + PDU
    return struct.pack(
        ">HHHBBHH", 1, 0, 6, 1, function, address, value_or_count
    )


def test_read_input_registers() -> None:
    store = RegisterStore()
    store.input_registers[4] = 215
    # MBAP header is 7 bytes (transaction, protocol, length, unit); the PDU
    # follows: response[7] = function echo, response[8] = byte count,
    # response[9:] = register values, each big-endian uint16.
    response = build_response(store, _request(4, 4, 3))  # regs 4-6 (direct addressing)
    assert response[7] == 4  # function echo (READ_INPUT)
    assert response[8] == 6  # byte count = 3 registers * 2 bytes
    values = struct.unpack(">HHH", response[9:15])
    assert values[0] == 215


def test_read_more_than_20_registers_is_error() -> None:
    store = RegisterStore()
    response = build_response(store, _request(4, 1, 21))
    assert response[7] == 0x84  # function | 0x80 -> exception
    assert response[8] == 0x02  # illegal data address


def test_write_single_register() -> None:
    store = RegisterStore()
    response = build_response(store, _request(6, 5, 999))  # holding reg 5
    assert store.holding_registers[5] == 999
    # Echo response
    assert response[7:] == struct.pack(">BHH", 6, 5, 999)[0:]
