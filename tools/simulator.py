"""Airfi device simulator: multicast announcements + Modbus TCP server.

Usage:
    uv run python tools/simulator.py [--port 5020] [--serial 12345678]
        [--device-type 1] [--no-announce]

Behaves like real hardware: at most 20 registers per read, one TCP client
at a time (later connections are closed immediately), announcements to
239.255.100.200:3000 every 2 seconds.
"""

from __future__ import annotations

import argparse
import asyncio
import socket
import struct

MULTICAST_GROUP = "239.255.100.200"
MULTICAST_PORT = 3000
MAX_REGISTERS_PER_READ = 20

READ_HOLDING = 3
READ_INPUT = 4
WRITE_SINGLE = 6

EXC_ILLEGAL_FUNCTION = 0x01
EXC_ILLEGAL_DATA_ADDRESS = 0x02


class RegisterStore:
    """Register values, keyed by 1-based address."""

    def __init__(self) -> None:
        self.input_registers: dict[int, int] = dict.fromkeys(range(1, 50), 0)
        self.holding_registers: dict[int, int] = dict.fromkeys(range(1, 69), 0)
        # Plausible defaults so HA shows something sensible.
        self.input_registers.update(
            {1: 3, 2: 17, 3: 1, 4: 52, 5: 215, 6: 221, 7: 68, 21: 1450, 22: 1390,
             23: 45}
        )
        self.holding_registers.update({1: 3, 5: 215, 8: 3, 12: 1})


def _exception(transaction: int, unit: int, function: int, code: int) -> bytes:
    pdu = struct.pack(">BB", function | 0x80, code)
    return struct.pack(">HHHB", transaction, 0, len(pdu) + 1, unit) + pdu


def build_response(store: RegisterStore, request: bytes) -> bytes:
    """Handle one Modbus TCP request frame; returns the response frame."""
    transaction, _protocol, _length, unit, function = struct.unpack(
        ">HHHBB", request[:8]
    )
    body = request[8:]
    if function in (READ_HOLDING, READ_INPUT):
        address, count = struct.unpack(">HH", body[:4])
        if count > MAX_REGISTERS_PER_READ:
            return _exception(
                transaction, unit, function, EXC_ILLEGAL_DATA_ADDRESS
            )
        table = (
            store.holding_registers
            if function == READ_HOLDING
            else store.input_registers
        )
        try:
            values = [table[address + 1 + i] for i in range(count)]
        except KeyError:
            return _exception(
                transaction, unit, function, EXC_ILLEGAL_DATA_ADDRESS
            )
        pdu = struct.pack(">BB", function, count * 2) + struct.pack(
            f">{count}H", *values
        )
        return struct.pack(">HHHB", transaction, 0, len(pdu) + 1, unit) + pdu
    if function == WRITE_SINGLE:
        address, value = struct.unpack(">HH", body[:4])
        if address + 1 not in store.holding_registers:
            return _exception(
                transaction, unit, function, EXC_ILLEGAL_DATA_ADDRESS
            )
        store.holding_registers[address + 1] = value
        pdu = struct.pack(">BHH", function, address, value)
        return struct.pack(">HHHB", transaction, 0, len(pdu) + 1, unit) + pdu
    return _exception(transaction, unit, function, EXC_ILLEGAL_FUNCTION)


class ModbusServer:
    """Single-client Modbus TCP server."""

    def __init__(self, store: RegisterStore) -> None:
        self._store = store
        self._active_client: asyncio.StreamWriter | None = None

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        if self._active_client is not None:
            print("Rejecting second client (single-client device)")
            writer.close()
            return
        self._active_client = writer
        peer = writer.get_extra_info("peername")
        print(f"Client connected: {peer}")
        try:
            while True:
                header = await reader.readexactly(6)
                _, _, length = struct.unpack(">HHH", header)
                rest = await reader.readexactly(length)
                response = build_response(self._store, header + rest)
                writer.write(response)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            print(f"Client disconnected: {peer}")
        finally:
            self._active_client = None
            writer.close()


async def announce_loop(port: int, serial: int, device_type: int) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    packet = struct.pack("<IHIBI", 0, 4000, serial, 1, device_type)
    sending = True
    while True:
        # No route to the multicast group (VPN, no network, macOS Local
        # Network permission) must not kill the loop — keep retrying so
        # announcements resume when the network allows them again.
        try:
            sock.sendto(packet, (MULTICAST_GROUP, MULTICAST_PORT))
            if not sending:
                print("Announcements resumed")
                sending = True
        except OSError as err:
            if sending:
                print(
                    f"Announcement send failed ({err}); will keep retrying. "
                    "Use --no-announce to silence, or check VPN/Local Network "
                    "permission. Manual entry still works without announcements."
                )
                sending = False
        await asyncio.sleep(2)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5020)
    parser.add_argument("--serial", type=int, default=12345678)
    parser.add_argument("--device-type", type=int, default=1)
    parser.add_argument("--no-announce", action="store_true")
    args = parser.parse_args()

    store = RegisterStore()
    server = ModbusServer(store)
    tcp = await asyncio.start_server(server.handle, "0.0.0.0", args.port)
    print(f"Modbus TCP on port {args.port}; serial {args.serial}")
    announce_task: asyncio.Task[None] | None = None
    if not args.no_announce:
        # Hold a reference so the task cannot be garbage-collected mid-run.
        announce_task = asyncio.ensure_future(
            announce_loop(args.port, args.serial, args.device_type)
        )
    try:
        async with tcp:
            await tcp.serve_forever()
    finally:
        if announce_task is not None:
            announce_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
