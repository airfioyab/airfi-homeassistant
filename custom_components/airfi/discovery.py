"""UDP multicast discovery of Airfi devices."""

from __future__ import annotations

import asyncio
import socket
import struct
from collections.abc import Callable
from dataclasses import dataclass

from .const import (
    ANNOUNCEMENT_FORMAT,
    ANNOUNCEMENT_SIZE,
    DISCOVERY_TIMEOUT,
    LOGGER,
    MULTICAST_GROUP,
    MULTICAST_PORT,
    model_name,
)


@dataclass(frozen=True)
class DiscoveredDevice:
    """An Airfi device seen on the network."""

    ip: str
    udp_port: int
    serial: int
    protocol_version: int
    device_type: int

    @property
    def model(self) -> str:
        """Human readable model name."""
        return model_name(self.device_type)


def parse_announcement(data: bytes, source_ip: str) -> DiscoveredDevice | None:
    """Parse a 15-byte announcement packet.

    The embedded IP field is ignored; the packet source address is
    authoritative and avoids firmware byte-order pitfalls.
    """
    if len(data) != ANNOUNCEMENT_SIZE:
        return None
    try:
        _ip, udp_port, serial, protocol_version, device_type = struct.unpack(
            ANNOUNCEMENT_FORMAT, data
        )
    except struct.error:
        return None
    return DiscoveredDevice(
        ip=source_ip,
        udp_port=udp_port,
        serial=serial,
        protocol_version=protocol_version,
        device_type=device_type,
    )


class _AnnouncementProtocol(asyncio.DatagramProtocol):
    """Feeds parsed announcements to a callback."""

    def __init__(self, on_device: Callable[[DiscoveredDevice], None]) -> None:
        self._on_device = on_device

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        device = parse_announcement(data, source_ip=addr[0])
        if device is not None:
            self._on_device(device)

    def error_received(self, exc: Exception) -> None:
        LOGGER.debug("Discovery socket error: %s", exc)


class AirfiDiscoveryListener:
    """Continuous multicast listener for Airfi announcements."""

    def __init__(self, on_device: Callable[[DiscoveredDevice], None]) -> None:
        self._on_device = on_device
        self._transport: asyncio.DatagramTransport | None = None

    async def async_start(self) -> None:
        """Open the multicast socket and start listening.

        Raises OSError if the multicast socket cannot be created, bound, or
        joined to the group.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", MULTICAST_PORT))
            mreq = struct.pack(
                "4sL", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY
            )
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.setblocking(False)
        except OSError:
            sock.close()
            raise

        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _AnnouncementProtocol(self._on_device), sock=sock
        )

    def stop(self) -> None:
        """Stop listening and close the socket."""
        if self._transport is not None:
            self._transport.close()
            self._transport = None


async def async_discover_devices(
    timeout: float = DISCOVERY_TIMEOUT,
) -> list[DiscoveredDevice]:
    """Listen for *timeout* seconds and return unique devices found."""
    found: dict[int, DiscoveredDevice] = {}
    listener = AirfiDiscoveryListener(lambda dev: found.setdefault(dev.serial, dev))
    try:
        await listener.async_start()
    except OSError as err:
        LOGGER.warning("Cannot open multicast discovery socket: %s", err)
        return []
    try:
        await asyncio.sleep(timeout)
    finally:
        listener.stop()
    return list(found.values())
