"""Tests for announcement parsing and discovery."""

import struct

from custom_components.airfi.discovery import DiscoveredDevice, parse_announcement


def _packet(
    ip: int = 0, port: int = 4000, serial: int = 12345678, ver: int = 1, model: int = 1
) -> bytes:
    return struct.pack("<IHIBI", ip, port, serial, ver, model)


def test_parse_valid_announcement() -> None:
    device = parse_announcement(_packet(), source_ip="192.168.1.50")
    assert device == DiscoveredDevice(
        ip="192.168.1.50",
        udp_port=4000,
        serial=12345678,
        protocol_version=1,
        device_type=1,
    )
    assert device.model == "Model 60 L"


def test_parse_uses_source_ip_not_payload_ip() -> None:
    device = parse_announcement(
        _packet(ip=0xC0A80101), source_ip="10.0.0.7"
    )
    assert device is not None
    assert device.ip == "10.0.0.7"


def test_parse_rejects_wrong_size() -> None:
    assert parse_announcement(b"\x00" * 14, source_ip="10.0.0.7") is None
    assert parse_announcement(b"\x00" * 16, source_ip="10.0.0.7") is None
    assert parse_announcement(b"", source_ip="10.0.0.7") is None
