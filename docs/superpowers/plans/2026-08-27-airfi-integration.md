# Airfi Home Assistant Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Home Assistant custom integration `airfi` that discovers Airfi air handling units via UDP multicast, polls them over Modbus TCP, and exposes every register as a typed HA entity.

**Architecture:** Declarative register descriptor tables drive one generic entity class per platform. One `DataUpdateCoordinator` per device performs connect-per-poll batched Modbus reads through a locked client wrapper. Config flow offers multicast discovery and manual entry. See `docs/superpowers/specs/2026-08-27-airfi-integration-design.md`.

**Tech Stack:** Python ≥3.13, pymodbus ≥3.9 <4.0, Home Assistant custom component, pytest + pytest-homeassistant-custom-component, uv for the venv.

## Global Constraints

- Integration domain: `airfi`. Code in `custom_components/airfi/`, tests in `tests/`.
- Max **20 registers per Modbus read**; batches: input `(1,20),(21,20),(41,9)`, holding `(1,20),(21,20),(41,20),(61,8)`.
- Only **one Modbus TCP client** at a time → connect-per-operation, everything behind one `asyncio.Lock` per device.
- Register numbers in spec/descriptors are **1-based**; pymodbus wire address = `register - 1`.
- Modbus TCP port fixed **502**; announcement multicast **239.255.100.200:3000**, packet `struct` format `"<IHIBI"`, 15 bytes; device IP = packet **source address** (ignore embedded IP field).
- Temperature registers are **signed** (int16 two's complement): raw > 0x7FFF → raw − 0x10000.
- Scan interval IS user-configurable (user requirement; deviates from HA core guideline — would be removed for upstream submission). Default 30 s, min 5, max 3600.
- No name/alias fields in config flows (HA guideline; HA built-in rename covers aliases).
- Entity naming via `_attr_has_entity_name = True` + `translation_key`; translations in en, fi, sv.
- The old prototype at `core/config/custom_components/airfi/` stays until Task 14 (Tasks 2–3 harvest from it), then is deleted.
- Commit messages: plain imperative style ("Add discovery module"), each ending with the line `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- All test functions fully type-annotated (HA convention).

## File Structure

```
custom_components/airfi/
    __init__.py        setup/unload, platform forwarding, rediscovery listener wiring
    const.py           domain, protocol constants, batches, DEVICE_MODELS map
    registers.py       descriptor dataclasses + full register tables + scaled_value()
    discovery.py       announcement parsing, one-shot discovery, continuous listener
    modbus.py          AirfiModbusClient (locked, connect-per-call, batched reads)
    coordinator.py     AirfiCoordinator (DataUpdateCoordinator) + device info
    entity.py          AirfiEntity base class
    sensor.py, binary_sensor.py, number.py, select.py, switch.py
    manifest.json, strings.json, translations/{en,fi,sv}.json
tests/
    conftest.py, test_const.py, test_registers.py, test_discovery.py,
    test_modbus.py, test_coordinator.py, test_init.py, test_sensor.py,
    test_binary_sensor.py, test_number.py, test_select.py, test_switch.py,
    test_config_flow.py, test_rediscovery.py, test_translations.py, test_simulator.py
tools/simulator.py     standalone device simulator
```

---

### Task 1: Dev environment and scaffolding

**Files:**
- Modify: `pyproject.toml`
- Create: `custom_components/airfi/__init__.py` (empty for now), `custom_components/airfi/manifest.json`, `custom_components/airfi/const.py` (minimal), `tests/__init__.py`, `tests/conftest.py`, `tests/test_const.py`, `.gitignore`

**Interfaces:**
- Produces: importable package `custom_components.airfi`, `const.DOMAIN = "airfi"`, working `pytest` run.

- [ ] **Step 1: Configure the project**

Replace `pyproject.toml` with:

```toml
[project]
name = "airfi-homeassistant"
version = "0.1.0"
description = "Home Assistant integration for Airfi air handling units"
requires-python = ">=3.13"
dependencies = ["pymodbus>=3.9.0,<4.0"]

[dependency-groups]
dev = [
    "pytest-homeassistant-custom-component",
    "ruff",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "ASYNC"]
```

Create `.gitignore`:

```
__pycache__/
.venv/
.pytest_cache/
.ruff_cache/
```

Run:
```bash
uv python pin 3.13 && uv sync
```
Expected: venv created, `pytest-homeassistant-custom-component` (which brings `homeassistant` and `pytest`) installed. If resolution fails on 3.13, try `uv python pin 3.14`.

- [ ] **Step 2: Write the failing test**

`tests/__init__.py`: empty file.

`tests/conftest.py`:
```python
"""Shared fixtures for the Airfi integration tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""
```

`tests/test_const.py`:
```python
"""Tests for const.py."""

from custom_components.airfi.const import DOMAIN


def test_domain() -> None:
    assert DOMAIN == "airfi"
```

Run: `uv run pytest tests/test_const.py -v`
Expected: FAIL (`ModuleNotFoundError: custom_components`)

- [ ] **Step 3: Create the package**

`custom_components/airfi/__init__.py`:
```python
"""The Airfi integration."""
```

`custom_components/airfi/const.py`:
```python
"""Constants for the Airfi integration."""

from __future__ import annotations

import logging

DOMAIN = "airfi"
LOGGER = logging.getLogger(__package__)
```

`custom_components/airfi/manifest.json`:
```json
{
  "domain": "airfi",
  "name": "Airfi",
  "codeowners": [],
  "config_flow": true,
  "documentation": "https://airfi.fi",
  "integration_type": "device",
  "iot_class": "local_polling",
  "requirements": ["pymodbus>=3.9.0,<4.0"],
  "version": "0.1.0"
}
```

Also create empty `custom_components/__init__.py`? **No** — `custom_components` must NOT contain an `__init__.py` (HA treats it as a namespace). If pytest cannot import, add `rootdir` handling by running pytest from the repo root (uv run does this).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_const.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock .gitignore custom_components tests
git commit -m "Add project scaffolding for the airfi custom component

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Protocol constants and model map (`const.py`)

**Files:**
- Modify: `custom_components/airfi/const.py`
- Test: `tests/test_const.py`

**Interfaces:**
- Produces: `DEFAULT_PORT=502`, `DEFAULT_SCAN_INTERVAL=30`, `MIN_SCAN_INTERVAL=5`, `MAX_SCAN_INTERVAL=3600`, `CONF_SCAN_INTERVAL="scan_interval"`, `CONF_SERIAL="serial"`, `CONF_DEVICE_TYPE="device_type"`, `MAX_REGISTERS_PER_READ=20`, `MULTICAST_GROUP`, `MULTICAST_PORT`, `ANNOUNCEMENT_FORMAT`, `ANNOUNCEMENT_SIZE`, `DISCOVERY_TIMEOUT=8`, `MODBUS_TIMEOUT=5`, `REG_INPUT="input"`, `REG_HOLDING="holding"`, `INPUT_REGISTER_BATCHES`, `HOLDING_REGISTER_BATCHES`, `DEVICE_MODELS: dict[int, str]`, `model_name(device_type: int) -> str`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_const.py`)

```python
from custom_components.airfi.const import (
    HOLDING_REGISTER_BATCHES,
    INPUT_REGISTER_BATCHES,
    MAX_REGISTERS_PER_READ,
    model_name,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_const.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement**

Append to `custom_components/airfi/const.py`:

```python
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SERIAL = "serial"
CONF_DEVICE_TYPE = "device_type"

# Modbus hardware constraints (see design spec).
MAX_REGISTERS_PER_READ = 20
MODBUS_TIMEOUT = 5

# UDP multicast discovery. Packet: IP (u32), UDP port (u16), serial (u32),
# protocol version (u8), device type (u32) — all little endian, 15 bytes.
MULTICAST_GROUP = "239.255.100.200"
MULTICAST_PORT = 3000
ANNOUNCEMENT_FORMAT = "<IHIBI"
ANNOUNCEMENT_SIZE = 15
DISCOVERY_TIMEOUT = 8

REG_INPUT = "input"
REG_HOLDING = "holding"

# (start, count) batches, 1-based, each within the 20-register device limit.
INPUT_REGISTER_BATCHES: list[tuple[int, int]] = [(1, 20), (21, 20), (41, 9)]
HOLDING_REGISTER_BATCHES: list[tuple[int, int]] = [
    (1, 20),
    (21, 20),
    (41, 20),
    (61, 8),
]
```

Then add `DEVICE_MODELS`, copied **verbatim** from `FanData.models` in `/Users/janekholm/Work/Airfi/airfi-sw/tools/fan_data.py` (IDs 0–38, e.g. `0: "Proto"`, `1: "Model 60 L"`, … `38: "Model 350 Ent R Water"` — copy all 39 entries exactly), followed by:

```python
def model_name(device_type: int) -> str:
    """Return the human readable model name for a device type id."""
    return DEVICE_MODELS.get(device_type, f"Airfi unit (type {device_type})")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_const.py -v` — Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/airfi/const.py tests/test_const.py
git commit -m "Add Airfi protocol constants and device model map

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Register descriptor tables (`registers.py`)

**Files:**
- Create: `custom_components/airfi/registers.py`
- Test: `tests/test_registers.py`
- Reference (read-only): `core/config/custom_components/airfi/const.py` (the prototype — harvest its tables)

**Interfaces:**
- Produces:
```python
@dataclass(frozen=True) class AirfiSensorRegister:      # address, key, register_type=REG_INPUT, scale=1.0, signed=False, unit=None, device_class=None, state_class=SensorStateClass.MEASUREMENT, entity_category=None, enabled_by_default=True, icon=None
@dataclass(frozen=True) class AirfiBinarySensorRegister:# address, key, register_type=REG_INPUT, bit=None, device_class=None, entity_category=None, enabled_by_default=True, icon=None
@dataclass(frozen=True) class AirfiNumberRegister:      # address, key, min_value, max_value, scale=1.0, step=1.0, unit=None, device_class=None, mode=NumberMode.AUTO, entity_category=None, enabled_by_default=True, icon=None
@dataclass(frozen=True) class AirfiSelectRegister:      # address, key, options: tuple[tuple[int, str], ...], entity_category=None, enabled_by_default=True, icon=None
@dataclass(frozen=True) class AirfiSwitchRegister:      # address, key, device_class=None, entity_category=None, enabled_by_default=True, icon=None
SENSOR_REGISTERS: tuple[AirfiSensorRegister, ...]
BINARY_SENSOR_REGISTERS: tuple[AirfiBinarySensorRegister, ...]
NUMBER_REGISTERS: tuple[AirfiNumberRegister, ...]
SELECT_REGISTERS: tuple[AirfiSelectRegister, ...]
SWITCH_REGISTERS: tuple[AirfiSwitchRegister, ...]
def scaled_value(raw: int, scale: float, signed: bool = False) -> float | int
```

- [ ] **Step 1: Write the failing tests**

`tests/test_registers.py`:
```python
"""Consistency tests for the register descriptor tables."""

from custom_components.airfi.const import REG_HOLDING, REG_INPUT
from custom_components.airfi.registers import (
    BINARY_SENSOR_REGISTERS,
    NUMBER_REGISTERS,
    SELECT_REGISTERS,
    SENSOR_REGISTERS,
    SWITCH_REGISTERS,
    scaled_value,
)


def test_input_register_coverage() -> None:
    """All input registers except unused 10 and reserved 20 are exposed."""
    addresses = {r.address for r in SENSOR_REGISTERS if r.register_type == REG_INPUT}
    addresses |= {
        r.address for r in BINARY_SENSOR_REGISTERS if r.register_type == REG_INPUT
    }
    assert addresses == set(range(1, 50)) - {10, 20}


def test_holding_register_coverage() -> None:
    """Every holding register 1–68 is exposed by exactly one writable platform."""
    numbers = [r.address for r in NUMBER_REGISTERS]
    selects = [r.address for r in SELECT_REGISTERS]
    switches = [r.address for r in SWITCH_REGISTERS]
    combined = numbers + selects + switches
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_registers.py -v` — Expected: FAIL (ImportError)

- [ ] **Step 3: Implement**

Create `custom_components/airfi/registers.py`. Start from the prototype file `core/config/custom_components/airfi/const.py` **lines 75–822** (the five dataclasses and the `SENSOR_REGISTERS`, `BINARY_SENSOR_REGISTERS`, `NUMBER_REGISTERS`, `SELECT_REGISTERS`, `SWITCH_REGISTERS` tables), copied over with these exact changes:

1. Module docstring: `"""Register descriptor tables for the Airfi integration — the single source of truth."""`; import `REG_HOLDING`, `REG_INPUT` from `.const` (do not redefine them here).
2. Rename the dataclass field `enabled_by_default` stays as-is; keep all field names unchanged.
3. Add field `signed: bool = False` to `AirfiSensorRegister` (after `scale`).
4. Set `signed=True` on every temperature sensor: addresses 4, 5, 6, 7, 8, 9, 28, 42.
5. Do NOT copy the prototype's `CLIMATE_*` constants (no climate entity) nor its
   `DOMAIN`/protocol constants (they live in `const.py` now).
6. Append at the end:

```python
def scaled_value(raw: int, scale: float, signed: bool = False) -> float | int:
    """Convert a raw 16-bit register value to its display value."""
    if signed and raw > 0x7FFF:
        raw -= 0x10000
    if scale == 1.0:
        return raw
    return round(raw * scale, 2)
```

Sanity notes for the copier: the prototype tables are known-good — 33 sensors,
14 binary sensors + 9 generated `error_e{n}` bit entries on address 32,
45 numbers, 8 selects, 12 switches. Keep the generated-bit list comprehension
for register 32 exactly as in the prototype.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_registers.py -v` — Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/airfi/registers.py tests/test_registers.py
git commit -m "Add declarative register descriptor tables

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Discovery (`discovery.py`)

**Files:**
- Create: `custom_components/airfi/discovery.py`
- Test: `tests/test_discovery.py`

**Interfaces:**
- Produces:
```python
@dataclass(frozen=True)
class DiscoveredDevice:
    ip: str; udp_port: int; serial: int; protocol_version: int; device_type: int
    @property
    def model(self) -> str  # via const.model_name

def parse_announcement(data: bytes, source_ip: str) -> DiscoveredDevice | None

class AirfiDiscoveryListener:
    def __init__(self, on_device: Callable[[DiscoveredDevice], None]) -> None
    async def async_start(self) -> None   # opens multicast socket; raises OSError on failure
    def stop(self) -> None

async def async_discover_devices(timeout: float = DISCOVERY_TIMEOUT) -> list[DiscoveredDevice]
```

- [ ] **Step 1: Write the failing tests**

`tests/test_discovery.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_discovery.py -v` — Expected: FAIL (ImportError)

- [ ] **Step 3: Implement**

`custom_components/airfi/discovery.py`:
```python
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

        Raises OSError if the socket cannot be created (e.g. port in use
        without SO_REUSEADDR support, or no network).
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", MULTICAST_PORT))
        mreq = struct.pack(
            "4sL", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setblocking(False)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_discovery.py -v` — Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/airfi/discovery.py tests/test_discovery.py
git commit -m "Add multicast discovery module

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Modbus client wrapper (`modbus.py`)

**Files:**
- Create: `custom_components/airfi/modbus.py`
- Test: `tests/test_modbus.py`

**Interfaces:**
- Produces:
```python
class AirfiConnectionError(Exception)
class AirfiModbusError(Exception)
type AirfiData = dict[str, dict[int, int]]  # {"input": {1-based addr: raw}, "holding": {...}}

class AirfiModbusClient:
    def __init__(self, host: str, port: int) -> None
    async def read_all(self) -> AirfiData
    async def read_input_register(self, address: int) -> int   # 1-based, for validation
    async def write_register(self, address: int, value: int) -> None  # 1-based
```
- Consumes: `INPUT_REGISTER_BATCHES`, `HOLDING_REGISTER_BATCHES`, `MODBUS_TIMEOUT`, `REG_INPUT`, `REG_HOLDING` from Task 2.

- [ ] **Step 1: Write the failing tests**

`tests/test_modbus.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_modbus.py -v` — Expected: FAIL (ImportError)

- [ ] **Step 3: Implement**

`custom_components/airfi/modbus.py`:
```python
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

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._lock = asyncio.Lock()
        self._client = AsyncModbusTcpClient(
            host=host, port=port, timeout=MODBUS_TIMEOUT
        )

    async def _connect(self) -> None:
        if not await self._client.connect():
            raise AirfiConnectionError(
                f"Cannot connect to Airfi device at {self._host}:{self._port}"
            )

    async def _read_batch(
        self,
        read: Callable[..., Awaitable[Any]],
        start: int,
        count: int,
    ) -> dict[int, int]:
        """Read one batch; returns {1-based address: raw value}."""
        result = await read(address=start - 1, count=count)
        if result.isError():
            raise AirfiModbusError(
                f"Modbus error reading registers {start}-{start + count - 1}: {result}"
            )
        return {start + i: value for i, value in enumerate(result.registers)}

    async def read_all(self) -> AirfiData:
        """Read every defined input and holding register."""
        async with self._lock:
            await self._connect()
            try:
                data: AirfiData = {REG_INPUT: {}, REG_HOLDING: {}}
                for start, count in INPUT_REGISTER_BATCHES:
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
                    address=address - 1, value=value
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_modbus.py -v` — Expected: PASS.
If pymodbus's actual signature rejects `count` as keyword, check the installed
version's `read_input_registers` signature (`uv run python -c "import inspect, pymodbus.client; print(inspect.signature(pymodbus.client.AsyncModbusTcpClient.read_input_registers))"`) and adjust call + test kwargs to match.

- [ ] **Step 5: Commit**

```bash
git add custom_components/airfi/modbus.py tests/test_modbus.py
git commit -m "Add locked connect-per-operation Modbus client

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Coordinator (`coordinator.py`)

**Files:**
- Create: `custom_components/airfi/coordinator.py`
- Test: `tests/test_coordinator.py`, add fixtures to `tests/conftest.py`

**Interfaces:**
- Produces:
```python
type AirfiConfigEntry = ConfigEntry[AirfiCoordinator]

class AirfiCoordinator(DataUpdateCoordinator[AirfiData]):
    def __init__(self, hass: HomeAssistant, config_entry: AirfiConfigEntry) -> None
    device_info: DeviceInfo                     # property
    async def async_write_value(self, address: int, raw_value: int) -> None
```
- Consumes: `AirfiModbusClient` (Task 5), const keys (Task 2).
- Config entry `data`: `{CONF_HOST, CONF_PORT, CONF_SERIAL?, CONF_DEVICE_TYPE?}`; `options`: `{CONF_SCAN_INTERVAL?}`; `unique_id`: serial as string, or `"host:port"` for manual entries.

- [ ] **Step 1: Add shared fixtures** (append to `tests/conftest.py`)

```python
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
```

- [ ] **Step 2: Write the failing tests**

`tests/test_coordinator.py`:
```python
"""Tests for the Airfi coordinator."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airfi.const import DOMAIN, REG_HOLDING
from custom_components.airfi.coordinator import AirfiCoordinator
from custom_components.airfi.modbus import AirfiConnectionError

from .conftest import make_data


async def test_update_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    mock_modbus_client.read_all.return_value = make_data(input_overrides={4: 215})
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data["input"][4] == 215


async def test_update_failure_wraps_client_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    mock_modbus_client.read_all.side_effect = AirfiConnectionError("nope")
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    assert not coordinator.last_update_success


async def test_device_info(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    mock_modbus_client.read_all.return_value = make_data(
        input_overrides={1: 3, 2: 17}
    )
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    info = coordinator.device_info
    assert info["identifiers"] == {(DOMAIN, "12345678")}
    assert info["manufacturer"] == "Airfi"
    assert info["model"] == "Model 60 L"
    assert info["hw_version"] == "3"
    assert info["sw_version"] == "17"


async def test_write_value_updates_cache_and_refreshes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    await coordinator.async_write_value(5, 215)
    mock_modbus_client.write_register.assert_awaited_once_with(5, 215)
    assert coordinator.data[REG_HOLDING][5] == 215


async def test_write_failure_raises_homeassistant_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    from homeassistant.exceptions import HomeAssistantError

    config_entry.add_to_hass(hass)
    coordinator = AirfiCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    mock_modbus_client.write_register.side_effect = AirfiConnectionError("nope")
    with pytest.raises(HomeAssistantError):
        await coordinator.async_write_value(5, 215)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_coordinator.py -v` — Expected: FAIL (ImportError)

- [ ] **Step 4: Implement**

`custom_components/airfi/coordinator.py`:
```python
"""Data update coordinator for one Airfi device."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DEVICE_TYPE,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    REG_HOLDING,
    REG_INPUT,
    model_name,
)
from .modbus import (
    AirfiConnectionError,
    AirfiData,
    AirfiModbusClient,
    AirfiModbusError,
)

type AirfiConfigEntry = ConfigEntry[AirfiCoordinator]


class AirfiCoordinator(DataUpdateCoordinator[AirfiData]):
    """Polls all registers of one Airfi device."""

    config_entry: AirfiConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: AirfiConfigEntry) -> None:
        """Initialize with connection parameters from the config entry."""
        scan_interval: int = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"Airfi {config_entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = AirfiModbusClient(
            config_entry.data[CONF_HOST], config_entry.data[CONF_PORT]
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Device registry entry shared by all this device's entities."""
        hw_version: int | None = None
        sw_version: int | None = None
        if self.data:
            hw_version = self.data[REG_INPUT].get(1)
            sw_version = self.data[REG_INPUT].get(2)
        device_type = self.config_entry.data.get(CONF_DEVICE_TYPE)
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.config_entry.unique_id or self.config_entry.entry_id)
            },
            name=self.config_entry.title,
            manufacturer="Airfi",
            model=model_name(device_type) if device_type is not None else None,
            hw_version=str(hw_version) if hw_version is not None else None,
            sw_version=str(sw_version) if sw_version is not None else None,
            configuration_url=f"http://{self.config_entry.data[CONF_HOST]}",
        )

    async def _async_update_data(self) -> AirfiData:
        """Read all registers from the device."""
        try:
            return await self.client.read_all()
        except (AirfiConnectionError, AirfiModbusError) as err:
            raise UpdateFailed(str(err)) from err

    async def async_write_value(self, address: int, raw_value: int) -> None:
        """Write one holding register, update the cache, and refresh."""
        try:
            await self.client.write_register(address, raw_value)
        except (AirfiConnectionError, AirfiModbusError) as err:
            raise HomeAssistantError(
                f"Writing register {address} failed: {err}"
            ) from err
        if self.data is not None:
            self.data[REG_HOLDING][address] = raw_value
            self.async_update_listeners()
        await self.async_request_refresh()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_coordinator.py -v` — Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add custom_components/airfi/coordinator.py tests/test_coordinator.py tests/conftest.py
git commit -m "Add per-device data update coordinator

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Integration setup and base entity (`__init__.py`, `entity.py`)

**Files:**
- Modify: `custom_components/airfi/__init__.py`
- Create: `custom_components/airfi/entity.py`
- Test: `tests/test_init.py`

**Interfaces:**
- Produces:
```python
# __init__.py
PLATFORMS = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]
async def async_setup_entry(hass: HomeAssistant, entry: AirfiConfigEntry) -> bool  # stores coordinator in entry.runtime_data
async def async_unload_entry(hass: HomeAssistant, entry: AirfiConfigEntry) -> bool

# entity.py
class AirfiEntity(CoordinatorEntity[AirfiCoordinator]):
    _attr_has_entity_name = True
    def __init__(self, coordinator: AirfiCoordinator, key: str,
                 entity_category, enabled_by_default: bool, icon: str | None) -> None
    # sets _attr_translation_key=key, _attr_unique_id=f"{unique_id_base}_{key}",
    # _attr_device_info, _attr_entity_category, _attr_entity_registry_enabled_default, _attr_icon
```

- [ ] **Step 1: Write the failing tests**

`tests/test_init.py`:
```python
"""Tests for integration setup and unload."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_device_unreachable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    from custom_components.airfi.modbus import AirfiConnectionError

    mock_modbus_client.read_all.side_effect = AirfiConnectionError("nope")
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_init.py -v` — Expected: FAIL (setup returns False / no config flow handler — the failure mode may be "Integration airfi not found" until `async_setup_entry` exists)

- [ ] **Step 3: Implement**

`custom_components/airfi/__init__.py`:
```python
"""The Airfi integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AirfiConfigEntry, AirfiCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: AirfiConfigEntry) -> bool:
    """Set up an Airfi device from a config entry."""
    coordinator = AirfiCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: AirfiConfigEntry) -> None:
    """Reload the entry when options (scan interval) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AirfiConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

`custom_components/airfi/entity.py`:
```python
"""Base entity for all Airfi platforms."""

from __future__ import annotations

from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AirfiCoordinator


class AirfiEntity(CoordinatorEntity[AirfiCoordinator]):
    """Common base: device info, naming, unique id."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirfiCoordinator,
        key: str,
        entity_category: EntityCategory | None,
        enabled_by_default: bool,
        icon: str | None,
    ) -> None:
        """Initialize from a register descriptor's common fields."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        base = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = coordinator.device_info
        self._attr_entity_category = entity_category
        self._attr_entity_registry_enabled_default = enabled_by_default
        if icon is not None:
            self._attr_icon = icon
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_init.py -v` — Expected: PASS (platform modules don't exist yet — `async_forward_entry_setups` with missing platform files will fail; if it does, create the five platform files now as minimal stubs, each containing only an `async_setup_entry(hass, entry, async_add_entities)` that does nothing, and note that Tasks 8–9 replace them.)

Stub content (identical for `sensor.py`, `binary_sensor.py`, `number.py`, `select.py`, `switch.py`, adjusting only the docstring):
```python
"""Airfi sensor platform."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AirfiConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for one Airfi device."""
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/airfi tests/test_init.py
git commit -m "Add config entry setup, base entity, and platform stubs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Read-only platforms (`sensor.py`, `binary_sensor.py`)

**Files:**
- Modify: `custom_components/airfi/sensor.py`, `custom_components/airfi/binary_sensor.py`
- Test: `tests/test_sensor.py`, `tests/test_binary_sensor.py`

**Interfaces:**
- Consumes: `SENSOR_REGISTERS`, `BINARY_SENSOR_REGISTERS`, `scaled_value` (Task 3), `AirfiEntity` (Task 7), coordinator data shape (Task 6).

- [ ] **Step 1: Write the failing tests**

`tests/test_sensor.py`:
```python
"""Tests for the sensor platform."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import make_data


async def _setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
    **overrides: dict[int, int],
) -> None:
    mock_modbus_client.read_all.return_value = make_data(**overrides)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_temperature_sensor_scaling(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    await _setup(
        hass, config_entry, mock_modbus_client, input_overrides={4: 215}
    )
    state = hass.states.get("sensor.model_60_l_12345678_outdoor_air_temperature")
    assert state is not None
    assert state.state == "21.5"
    assert state.attributes["unit_of_measurement"] == "°C"


async def test_negative_temperature(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    await _setup(
        hass, config_entry, mock_modbus_client, input_overrides={4: 0xFFCE}
    )
    state = hass.states.get("sensor.model_60_l_12345678_outdoor_air_temperature")
    assert state is not None
    assert state.state == "-5.0"


async def test_unscaled_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    await _setup(
        hass, config_entry, mock_modbus_client, input_overrides={21: 1450}
    )
    state = hass.states.get("sensor.model_60_l_12345678_supply_fan_rpm")
    assert state is not None
    assert state.state == "1450"
```

Note: entity_ids derive from the device name (entry title `Model 60 L 12345678`)
plus the English entity name. After implementing, if the ids differ, print them
with `hass.states.async_entity_ids("sensor")` in a temporary assert message and
fix the test ids — do not weaken the value assertions. Translations don't exist
yet, so HA falls back to the translation key as the object id; that is expected
and stable for tests.

`tests/test_binary_sensor.py`:
```python
"""Tests for the binary sensor platform."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import make_data


async def test_plain_and_bitmask_binary_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    mock_modbus_client.read_all.return_value = make_data(
        input_overrides={15: 1, 32: 0b101}  # fireplace on; errors E0 and E2 set
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    prefix = "binary_sensor.model_60_l_12345678"
    assert hass.states.get(f"{prefix}_fireplace_active").state == "on"
    assert hass.states.get(f"{prefix}_error_e0").state == "on"
    assert hass.states.get(f"{prefix}_error_e1").state == "off"
    assert hass.states.get(f"{prefix}_error_e2").state == "on"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sensor.py tests/test_binary_sensor.py -v`
Expected: FAIL (states are None — stubs create no entities)

- [ ] **Step 3: Implement**

Replace `custom_components/airfi/sensor.py`:
```python
"""Airfi sensor platform."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .entity import AirfiEntity
from .registers import SENSOR_REGISTERS, AirfiSensorRegister, scaled_value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for one Airfi device."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirfiSensor(coordinator, description) for description in SENSOR_REGISTERS
    )


class AirfiSensor(AirfiEntity, SensorEntity):
    """A sensor backed by one register."""

    def __init__(
        self, coordinator: AirfiCoordinator, description: AirfiSensorRegister
    ) -> None:
        """Initialize from a register descriptor."""
        super().__init__(
            coordinator,
            description.key,
            description.entity_category,
            description.enabled_by_default,
            description.icon,
        )
        self._description = description
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class

    @property
    def native_value(self) -> float | int | None:
        """Scaled register value."""
        desc = self._description
        raw = self.coordinator.data[desc.register_type].get(desc.address)
        if raw is None:
            return None
        return scaled_value(raw, desc.scale, desc.signed)
```

Replace `custom_components/airfi/binary_sensor.py`:
```python
"""Airfi binary sensor platform."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .entity import AirfiEntity
from .registers import BINARY_SENSOR_REGISTERS, AirfiBinarySensorRegister


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for one Airfi device."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirfiBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_REGISTERS
    )


class AirfiBinarySensor(AirfiEntity, BinarySensorEntity):
    """A binary sensor backed by a register or a bit within one."""

    def __init__(
        self, coordinator: AirfiCoordinator, description: AirfiBinarySensorRegister
    ) -> None:
        """Initialize from a register descriptor."""
        super().__init__(
            coordinator,
            description.key,
            description.entity_category,
            description.enabled_by_default,
            description.icon,
        )
        self._description = description
        self._attr_device_class = description.device_class

    @property
    def is_on(self) -> bool | None:
        """True when the register (or its bit) is non-zero."""
        desc = self._description
        raw = self.coordinator.data[desc.register_type].get(desc.address)
        if raw is None:
            return None
        if desc.bit is not None:
            return bool(raw & (1 << desc.bit))
        return raw != 0
```

Diagnostic/config entities are disabled by default, so tests asserting them must
target enabled ones (all entities used in the tests above are enabled-tier).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sensor.py tests/test_binary_sensor.py -v` — Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/airfi/sensor.py custom_components/airfi/binary_sensor.py tests/test_sensor.py tests/test_binary_sensor.py
git commit -m "Add sensor and binary sensor platforms

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Writable platforms (`number.py`, `select.py`, `switch.py`)

**Files:**
- Modify: `custom_components/airfi/number.py`, `custom_components/airfi/select.py`, `custom_components/airfi/switch.py`
- Test: `tests/test_number.py`, `tests/test_select.py`, `tests/test_switch.py`

**Interfaces:**
- Consumes: `NUMBER_REGISTERS`, `SELECT_REGISTERS`, `SWITCH_REGISTERS`, `scaled_value` (Task 3); `AirfiCoordinator.async_write_value(address, raw_value)` (Task 6). All writes go through the coordinator; display→raw conversion is `raw = round(value / scale)` clamped to `[min_value/scale... no —` **clamp in raw domain**: `raw = max(round(min_value / scale), min(round(max_value / scale), round(value / scale)))`.

- [ ] **Step 1: Write the failing tests**

`tests/test_number.py`:
```python
"""Tests for the number platform."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import make_data


async def test_setpoint_read_and_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    mock_modbus_client.read_all.return_value = make_data(
        holding_overrides={5: 215}
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "number.model_60_l_12345678_temperature_setpoint"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "21.5"
    assert state.attributes["min"] == 17.0
    assert state.attributes["max"] == 26.0

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 22.0},
        blocking=True,
    )
    mock_modbus_client.write_register.assert_awaited_with(5, 220)
```

`tests/test_select.py`:
```python
"""Tests for the select platform."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import make_data


async def test_speed_select_read_and_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    mock_modbus_client.read_all.return_value = make_data(holding_overrides={1: 3})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "select.model_60_l_12345678_speed"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "speed_3"
    assert state.attributes["options"] == [
        "off",
        "speed_1",
        "speed_2",
        "speed_3",
        "speed_4",
        "speed_5",
    ]

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "speed_5"},
        blocking=True,
    )
    mock_modbus_client.write_register.assert_awaited_with(1, 5)
```

`tests/test_switch.py`:
```python
"""Tests for the switch platform."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import make_data


async def test_sauna_switch_read_and_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    mock_modbus_client.read_all.return_value = make_data(holding_overrides={57: 0})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "switch.model_60_l_12345678_sauna_mode"
    assert hass.states.get(entity_id).state == "off"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    mock_modbus_client.write_register.assert_awaited_with(57, 1)
    assert hass.states.get(entity_id).state == "on"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    mock_modbus_client.write_register.assert_awaited_with(57, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_number.py tests/test_select.py tests/test_switch.py -v`
Expected: FAIL (no entities)

- [ ] **Step 3: Implement**

Replace `custom_components/airfi/number.py`:
```python
"""Airfi number platform — writable numeric holding registers."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import REG_HOLDING
from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .entity import AirfiEntity
from .registers import NUMBER_REGISTERS, AirfiNumberRegister, scaled_value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities for one Airfi device."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirfiNumber(coordinator, description) for description in NUMBER_REGISTERS
    )


class AirfiNumber(AirfiEntity, NumberEntity):
    """A writable numeric register."""

    def __init__(
        self, coordinator: AirfiCoordinator, description: AirfiNumberRegister
    ) -> None:
        """Initialize from a register descriptor."""
        super().__init__(
            coordinator,
            description.key,
            description.entity_category,
            description.enabled_by_default,
            description.icon,
        )
        self._description = description
        self._attr_native_min_value = description.min_value
        self._attr_native_max_value = description.max_value
        self._attr_native_step = description.step
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class
        self._attr_mode = description.mode

    @property
    def native_value(self) -> float | int | None:
        """Scaled register value."""
        desc = self._description
        raw = self.coordinator.data[REG_HOLDING].get(desc.address)
        if raw is None:
            return None
        return scaled_value(raw, desc.scale)

    async def async_set_native_value(self, value: float) -> None:
        """Convert to raw, clamp to the device's limits, and write."""
        desc = self._description
        raw = round(value / desc.scale)
        raw_min = round(desc.min_value / desc.scale)
        raw_max = round(desc.max_value / desc.scale)
        raw = max(raw_min, min(raw_max, raw))
        await self.coordinator.async_write_value(desc.address, raw)
```

Replace `custom_components/airfi/select.py`:
```python
"""Airfi select platform — holding registers with discrete options."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import REG_HOLDING
from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .entity import AirfiEntity
from .registers import SELECT_REGISTERS, AirfiSelectRegister


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities for one Airfi device."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirfiSelect(coordinator, description) for description in SELECT_REGISTERS
    )


class AirfiSelect(AirfiEntity, SelectEntity):
    """A writable register with named discrete values."""

    def __init__(
        self, coordinator: AirfiCoordinator, description: AirfiSelectRegister
    ) -> None:
        """Initialize from a register descriptor."""
        super().__init__(
            coordinator,
            description.key,
            description.entity_category,
            description.enabled_by_default,
            description.icon,
        )
        self._description = description
        self._raw_to_option = dict(description.options)
        self._option_to_raw = {opt: raw for raw, opt in description.options}
        self._attr_options = [opt for _, opt in description.options]

    @property
    def current_option(self) -> str | None:
        """Option matching the current register value."""
        raw = self.coordinator.data[REG_HOLDING].get(self._description.address)
        return self._raw_to_option.get(raw)

    async def async_select_option(self, option: str) -> None:
        """Write the raw value for the chosen option."""
        await self.coordinator.async_write_value(
            self._description.address, self._option_to_raw[option]
        )
```

Replace `custom_components/airfi/switch.py`:
```python
"""Airfi switch platform — boolean holding registers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import REG_HOLDING
from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .entity import AirfiEntity
from .registers import SWITCH_REGISTERS, AirfiSwitchRegister


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities for one Airfi device."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirfiSwitch(coordinator, description) for description in SWITCH_REGISTERS
    )


class AirfiSwitch(AirfiEntity, SwitchEntity):
    """A writable 0/1 register."""

    def __init__(
        self, coordinator: AirfiCoordinator, description: AirfiSwitchRegister
    ) -> None:
        """Initialize from a register descriptor."""
        super().__init__(
            coordinator,
            description.key,
            description.entity_category,
            description.enabled_by_default,
            description.icon,
        )
        self._description = description
        self._attr_device_class = description.device_class

    @property
    def is_on(self) -> bool | None:
        """True when the register is non-zero."""
        raw = self.coordinator.data[REG_HOLDING].get(self._description.address)
        if raw is None:
            return None
        return raw != 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Write 1."""
        await self.coordinator.async_write_value(self._description.address, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Write 0."""
        await self.coordinator.async_write_value(self._description.address, 0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_number.py tests/test_select.py tests/test_switch.py -v` — Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/airfi/number.py custom_components/airfi/select.py custom_components/airfi/switch.py tests/test_number.py tests/test_select.py tests/test_switch.py
git commit -m "Add number, select, and switch platforms

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Config flow and options flow (`config_flow.py`)

**Files:**
- Create: `custom_components/airfi/config_flow.py`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Consumes: `async_discover_devices`, `DiscoveredDevice` (Task 4); `AirfiModbusClient.read_input_register` (Task 5); const keys (Task 2).
- Produces: `AirfiConfigFlow` (menu → discover/manual), `AirfiOptionsFlow` (scan interval). Entry data `{CONF_HOST, CONF_PORT, CONF_SERIAL?, CONF_DEVICE_TYPE?}`; discovered entries: `unique_id=str(serial)`, title `f"{model} {serial}"`; manual entries: `unique_id=f"{host}:{port}"`, title `f"Airfi {host}"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_config_flow.py`:
```python
"""Tests for the Airfi config and options flows."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airfi.const import (
    CONF_DEVICE_TYPE,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL,
    DOMAIN,
)
from custom_components.airfi.discovery import DiscoveredDevice

DEVICE = DiscoveredDevice(
    ip="192.168.1.50", udp_port=4000, serial=12345678, protocol_version=1, device_type=1
)


async def test_discovery_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.MENU

    with patch(
        "custom_components.airfi.config_flow.async_discover_devices",
        AsyncMock(return_value=[DEVICE]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )
        # Progress step: drive it to completion.
        while result["type"] is FlowResultType.SHOW_PROGRESS:
            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"]
            )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "12345678"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Model 60 L 12345678"
    assert result["data"] == {
        "host": "192.168.1.50",
        "port": 502,
        CONF_SERIAL: 12345678,
        CONF_DEVICE_TYPE: 1,
    }
    assert result["result"].unique_id == "12345678"


async def test_discovery_excludes_configured_serials(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="12345678", data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch(
        "custom_components.airfi.config_flow.async_discover_devices",
        AsyncMock(return_value=[DEVICE]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )
        while result["type"] is FlowResultType.SHOW_PROGRESS:
            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"]
            )
    # Only device already configured → falls through to manual entry.
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_manual_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["step_id"] == "manual"

    with patch(
        "custom_components.airfi.config_flow.AirfiModbusClient", autospec=True
    ) as client_cls:
        client_cls.return_value.read_input_register = AsyncMock(return_value=1)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "10.0.0.9", "port": 502}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airfi 10.0.0.9"
    assert result["data"] == {"host": "10.0.0.9", "port": 502}
    assert result["result"].unique_id == "10.0.0.9:502"


async def test_manual_flow_cannot_connect(hass: HomeAssistant) -> None:
    from custom_components.airfi.modbus import AirfiConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with patch(
        "custom_components.airfi.config_flow.AirfiModbusClient", autospec=True
    ) as client_cls:
        client_cls.return_value.read_input_register = AsyncMock(
            side_effect=AirfiConnectionError("nope")
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "10.0.0.9", "port": 502}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_SCAN_INTERVAL] == 60
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config_flow.py -v` — Expected: FAIL (no flow handler)

- [ ] **Step 3: Implement**

`custom_components/airfi/config_flow.py`:
```python
"""Config flow and options flow for the Airfi integration."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_TYPE,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .discovery import DiscoveredDevice, async_discover_devices
from .modbus import AirfiConnectionError, AirfiModbusClient, AirfiModbusError

_PORT_SELECTOR = vol.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=65535, step=1, mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Coerce(int),
)

STEP_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): _PORT_SELECTOR,
    }
)


async def _validate_connection(host: str, port: int) -> str | None:
    """Try reading input register 1; return an error key or None."""
    client = AirfiModbusClient(host, port)
    try:
        await client.read_input_register(1)
    except AirfiConnectionError:
        return "cannot_connect"
    except AirfiModbusError:
        return "modbus_error"
    return None


class AirfiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Discover-or-manual config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._devices: dict[str, DiscoveredDevice] = {}
        self._discovery_task: asyncio.Task[list[DiscoveredDevice]] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer discovery or manual entry."""
        return self.async_show_menu(
            step_id="user", menu_options=["discover", "manual"]
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Listen for announcements, then present the found devices."""
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(
                async_discover_devices()
            )
        if not self._discovery_task.done():
            return self.async_show_progress(
                step_id="discover",
                progress_action="discovering",
                progress_task=self._discovery_task,
            )

        try:
            devices = self._discovery_task.result()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Discovery failed")
            devices = []

        known_ids = self._async_current_ids(include_ignore=True)
        self._devices = {
            str(dev.serial): dev
            for dev in devices
            if str(dev.serial) not in known_ids
        }
        if not self._devices:
            return self.async_show_progress_done(next_step_id="manual")
        return self.async_show_progress_done(next_step_id="select_device")

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create an entry for the chosen discovered device."""
        if user_input is not None:
            device = self._devices[user_input["device"]]
            await self.async_set_unique_id(str(device.serial))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{device.model} {device.serial}",
                data={
                    CONF_HOST: device.ip,
                    CONF_PORT: DEFAULT_PORT,
                    CONF_SERIAL: device.serial,
                    CONF_DEVICE_TYPE: device.device_type,
                },
            )

        options = [
            selector.SelectOptionDict(
                value=serial,
                label=f"{dev.model} (SN {dev.serial}) — {dev.ip}",
            )
            for serial, dev in self._devices.items()
        ]
        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual host and port entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host: str = user_input[CONF_HOST].strip()
            port: int = user_input.get(CONF_PORT, DEFAULT_PORT)
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()
            error = await _validate_connection(host, port)
            if error is None:
                return self.async_create_entry(
                    title=f"Airfi {host}",
                    data={CONF_HOST: host, CONF_PORT: port},
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="manual", data_schema=STEP_MANUAL_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AirfiOptionsFlow:
        """Return the options flow handler."""
        return AirfiOptionsFlow()


class AirfiOptionsFlow(OptionsFlow):
    """Scan interval option."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current: int = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=MIN_SCAN_INTERVAL,
                                max=MAX_SCAN_INTERVAL,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Coerce(int),
                    )
                }
            ),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_flow.py -v` — Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/airfi/config_flow.py tests/test_config_flow.py
git commit -m "Add config flow with discovery, manual entry, and options

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: Rediscovery listener (host updates)

**Files:**
- Modify: `custom_components/airfi/__init__.py`
- Test: `tests/test_rediscovery.py`; modify `tests/conftest.py` (mock the listener in existing setup tests)

**Interfaces:**
- Consumes: `AirfiDiscoveryListener`, `DiscoveredDevice` (Task 4).
- Produces: while any entry is loaded, a shared `AirfiDiscoveryListener` runs; announcements matching a configured serial with a changed host update `entry.data[CONF_HOST]` and reload the entry; announcements matching a manual entry's host upgrade its `unique_id`/data with the serial and device type. Stored in `hass.data[DOMAIN]["discovery_listener"]`.

- [ ] **Step 1: Keep existing tests green** — add to `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def mock_discovery_listener() -> Generator[AsyncMock]:
    """Prevent real multicast sockets in tests; capture the callback."""
    with patch(
        "custom_components.airfi.AirfiDiscoveryListener", autospec=True
    ) as listener_cls:
        yield listener_cls
```

- [ ] **Step 2: Write the failing tests**

`tests/test_rediscovery.py`:
```python
"""Tests for automatic host updates from announcements."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airfi.const import CONF_DEVICE_TYPE, CONF_SERIAL
from custom_components.airfi.discovery import DiscoveredDevice


def _get_callback(mock_discovery_listener: AsyncMock):
    return mock_discovery_listener.call_args.args[0]


async def test_host_update_on_new_ip(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
    mock_discovery_listener: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    on_device = _get_callback(mock_discovery_listener)
    on_device(
        DiscoveredDevice(
            ip="192.168.1.99",
            udp_port=4000,
            serial=12345678,
            protocol_version=1,
            device_type=1,
        )
    )
    await hass.async_block_till_done()
    assert config_entry.data["host"] == "192.168.1.99"


async def test_manual_entry_upgraded_with_serial(
    hass: HomeAssistant,
    mock_modbus_client: AsyncMock,
    mock_discovery_listener: AsyncMock,
) -> None:
    from custom_components.airfi.const import DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Airfi 192.168.1.50",
        unique_id="192.168.1.50:502",
        data={"host": "192.168.1.50", "port": 502},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    on_device = _get_callback(mock_discovery_listener)
    on_device(
        DiscoveredDevice(
            ip="192.168.1.50",
            udp_port=4000,
            serial=87654321,
            protocol_version=1,
            device_type=3,
        )
    )
    await hass.async_block_till_done()
    assert entry.unique_id == "87654321"
    assert entry.data[CONF_SERIAL] == 87654321
    assert entry.data[CONF_DEVICE_TYPE] == 3
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_rediscovery.py -v` — Expected: FAIL (`AirfiDiscoveryListener` not imported in `__init__`, callback never registered)

- [ ] **Step 4: Implement** — modify `custom_components/airfi/__init__.py`; full new content:

```python
"""The Airfi integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback

from .const import CONF_DEVICE_TYPE, CONF_SERIAL, DOMAIN, LOGGER
from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .discovery import AirfiDiscoveryListener, DiscoveredDevice

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: AirfiConfigEntry) -> bool:
    """Set up an Airfi device from a config entry."""
    coordinator = AirfiCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await _async_ensure_discovery_listener(hass)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: AirfiConfigEntry) -> None:
    """Reload the entry when options (scan interval) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AirfiConfigEntry) -> bool:
    """Unload a config entry; stop discovery when the last one unloads."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    remaining = [
        other
        for other in hass.config_entries.async_loaded_entries(DOMAIN)
        if other.entry_id != entry.entry_id
    ]
    if not remaining and (data := hass.data.get(DOMAIN)):
        listener: AirfiDiscoveryListener = data.pop("discovery_listener", None)
        if listener is not None:
            listener.stop()
    return unloaded


async def _async_ensure_discovery_listener(hass: HomeAssistant) -> None:
    """Start the shared announcement listener once."""
    data = hass.data.setdefault(DOMAIN, {})
    if "discovery_listener" in data:
        return

    @callback
    def _on_device(device: DiscoveredDevice) -> None:
        _async_handle_announcement(hass, device)

    listener = AirfiDiscoveryListener(_on_device)
    try:
        await listener.async_start()
    except OSError as err:
        LOGGER.warning("Rediscovery listener could not start: %s", err)
        return
    data["discovery_listener"] = listener


@callback
def _async_handle_announcement(hass: HomeAssistant, device: DiscoveredDevice) -> None:
    """Update configured entries from a received announcement."""
    serial_id = str(device.serial)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == serial_id:
            if entry.data[CONF_HOST] != device.ip:
                LOGGER.info(
                    "Airfi %s moved to %s; updating", serial_id, device.ip
                )
                hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_HOST: device.ip}
                )
                hass.async_create_task(
                    hass.config_entries.async_reload(entry.entry_id)
                )
            return
    # No serial match: upgrade a manual entry for this host.
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data.get(CONF_HOST) == device.ip
            and entry.data.get(CONF_SERIAL) is None
        ):
            LOGGER.info(
                "Upgrading manual entry %s with serial %s", device.ip, serial_id
            )
            hass.config_entries.async_update_entry(
                entry,
                unique_id=serial_id,
                data={
                    **entry.data,
                    CONF_SERIAL: device.serial,
                    CONF_DEVICE_TYPE: device.device_type,
                },
            )
            return
```

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -v`
Expected: ALL PASS (the autouse `mock_discovery_listener` keeps earlier tests hermetic)

- [ ] **Step 6: Commit**

```bash
git add custom_components/airfi/__init__.py tests/test_rediscovery.py tests/conftest.py
git commit -m "Add background rediscovery with automatic host updates

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: Translations (`strings.json`, en/fi/sv)

**Files:**
- Create: `custom_components/airfi/strings.json`, `custom_components/airfi/translations/en.json`, `custom_components/airfi/translations/fi.json`, `custom_components/airfi/translations/sv.json`
- Test: `tests/test_translations.py`

- [ ] **Step 1: Write the failing test**

`tests/test_translations.py`:
```python
"""Every register key must have a translated name in every language."""

import json
import pathlib

import pytest

from custom_components.airfi.registers import (
    BINARY_SENSOR_REGISTERS,
    NUMBER_REGISTERS,
    SELECT_REGISTERS,
    SENSOR_REGISTERS,
    SWITCH_REGISTERS,
)

TRANSLATIONS = pathlib.Path("custom_components/airfi/translations")

PLATFORM_TABLES = {
    "sensor": SENSOR_REGISTERS,
    "binary_sensor": BINARY_SENSOR_REGISTERS,
    "number": NUMBER_REGISTERS,
    "select": SELECT_REGISTERS,
    "switch": SWITCH_REGISTERS,
}


@pytest.mark.parametrize("language", ["en", "fi", "sv"])
def test_all_register_keys_translated(language: str) -> None:
    data = json.loads((TRANSLATIONS / f"{language}.json").read_text())
    entities = data["entity"]
    for platform, table in PLATFORM_TABLES.items():
        translated = entities[platform]
        for register in table:
            assert register.key in translated, (
                f"{language}: missing {platform}.{register.key}"
            )
            assert translated[register.key]["name"]


@pytest.mark.parametrize("language", ["en", "fi", "sv"])
def test_select_options_translated(language: str) -> None:
    data = json.loads((TRANSLATIONS / f"{language}.json").read_text())
    selects = data["entity"]["select"]
    for register in SELECT_REGISTERS:
        state = selects[register.key]["state"]
        for _, option in register.options:
            assert option in state, (
                f"{language}: missing option {register.key}.{option}"
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_translations.py -v` — Expected: FAIL (files missing)

- [ ] **Step 3: Write the translation files**

Structure of each file (HA custom-component translation format):

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Add Airfi device",
        "menu_options": {
          "discover": "Search the network automatically",
          "manual": "Enter address manually"
        }
      },
      "select_device": {
        "title": "Select device",
        "data": { "device": "Discovered devices" }
      },
      "manual": {
        "title": "Manual connection",
        "data": { "host": "IP address", "port": "Port" }
      }
    },
    "progress": { "discovering": "Listening for Airfi devices…" },
    "error": {
      "cannot_connect": "Cannot connect to the device",
      "modbus_error": "The device rejected the Modbus request"
    },
    "abort": { "already_configured": "This device is already configured" }
  },
  "options": {
    "step": {
      "init": {
        "title": "Airfi options",
        "data": { "scan_interval": "Polling interval (seconds)" }
      }
    }
  },
  "entity": {
    "sensor": { "outdoor_air_temperature": { "name": "Outdoor air temperature (T1)" }, ... },
    "binary_sensor": { ... },
    "number": { ... },
    "select": {
      "speed": {
        "name": "Fan speed",
        "state": { "off": "Off", "speed_1": "Speed 1", ... }
      }, ...
    },
    "switch": { ... }
  }
}
```

`strings.json` is identical to `en.json` (copy it). Fill every `entity` section
from this name table — one entry per register key. English and Swedish names
translate the Finnish spec names; Finnish names come from `Specification.md`
verbatim (minus register prefixes like "T1," which move into parentheses).

| key | en | fi | sv |
|---|---|---|---|
| hardware_version | Hardware version | Airfi-hw versio | Hårdvaruversion |
| software_version | Software version | Airfi-sw versio | Mjukvaruversion |
| modbus_register_version | Modbus register version | Modbus-rekisteriversio | Modbus-registerversion |
| outdoor_air_temperature | Outdoor air temperature (T1) | Ulkoilman lämpötila (T1) | Uteluftens temperatur (T1) |
| supply_air_temperature | Supply air temperature (T2) | Tuloilman lämpötila (T2) | Tilluftens temperatur (T2) |
| exhaust_air_temperature | Extract air temperature (T3) | Poistoilman lämpötila (T3) | Frånluftens temperatur (T3) |
| waste_air_temperature | Waste air temperature (T4) | Jäteilman lämpötila (T4) | Avluftens temperatur (T4) |
| supply_air_apartment_temperature | Supply to apartment temperature (T5) | Tulo asuntoon lämpötila (T5) | Tillluft till bostaden (T5) |
| freeze_protection_temperature | Freeze protection temperature (T6) | Jäätymissuojan lämpötila (T6) | Frysskyddstemperatur (T6) |
| exhaust_fan_speed | Extract fan speed | Poistopuhaltimen nopeus | Frånluftsfläktens hastighet |
| supply_fan_speed | Supply fan speed | Tulopuhaltimen nopeus | Tilluftsfläktens hastighet |
| aux3_mode | AUX3 mode | AUX3-tila | AUX3-läge |
| aux4_mode | AUX4 mode | AUX4-tila | AUX4-läge |
| fireplace_active | Fireplace mode active | Takkatoiminto | Braskaminläge aktivt |
| home_away_state | Home | Kotona/Poissa-tila | Hemma |
| emergency_stop | Emergency stop | Hätäseis-tila | Nödstopp |
| freeze_alarm | Freeze risk alarm | Jäätymisvaarahälytys | Frysrisklarm |
| machine_fault | Machine fault | Koneen vikatila | Maskinfel |
| supply_fan_rpm | Supply fan RPM | Tulopuhaltimen RPM | Tilluftsfläktens varvtal |
| exhaust_fan_rpm | Extract fan RPM | Poistopuhaltimen RPM | Frånluftsfläktens varvtal |
| humidity | Humidity | Mitattu kosteuspitoisuus | Luftfuktighet |
| fan_speed_output | Fan speed output | Puhaltimen nopeus | Fläkthastighet ut |
| force_control_state | Force control state | Pakko-ohjaus | Tvångsstyrningens läge |
| direct_control_active | Direct control active | Suoraohjaus päällä | Direktstyrning aktiv |
| direct_control_percentage | Direct control | Suoraohjaus 0–100 % | Direktstyrning |
| temperature_setpoint_readback | Temperature setpoint (device) | Lämpötilan asetuspiste (laite) | Temperaturbörvärde (enhet) |
| aux3_setpoint_readback | AUX3 setpoint (device) | AUX3-asetuspiste (laite) | AUX3-börvärde (enhet) |
| aux4_setpoint_readback | AUX4 setpoint (device) | AUX4-asetuspiste (laite) | AUX4-börvärde (enhet) |
| filter_change_interval_readback | Filter change interval (device) | Suodattimen vaihtoväli (laite) | Filterbytesintervall (enhet) |
| error_e0 … error_e8 | Error E0 … Error E8 | Vika E0 … Vika E8 | Fel E0 … Fel E8 |
| aux3_read_value | AUX3 value | AUX3 luettu arvo | AUX3-värde |
| aux4_read_value | AUX4 value | AUX4 luettu arvo | AUX4-värde |
| constant_pressure_supply_alarm | Constant pressure supply alarm | Vakiopainesäätö tulo -hälytys | Konstanttryck tilluft-larm |
| constant_pressure_exhaust_alarm | Constant pressure extract alarm | Vakiopainesäätö poisto -hälytys | Konstanttryck frånluft-larm |
| filter_guard_alarm | Filter guard alarm | Suodatinvahtihälytys | Filtervaktslarm |
| aux2_state | AUX2 state | AUX2-tila | AUX2-läge |
| fire_alarm | Fire alarm | Palohälytys | Brandlarm |
| range_hood_compensation | Range hood compensation | Liesikuvun kompensointi | Spiskåpskompensering |
| s1_read_value | S1 value | S1 luettu arvo | S1-värde |
| room_sensor | Room temperature | Huone-anturi | Rumstemperatur |
| post_heat_valve | Post-heating valve | Jälkilämmitysventtiili | Eftervärmningsventil |
| defrost_active | Defrost active | Sulatus päällä | Avfrostning aktiv |
| intake_pressure | Intake pressure | Tulopaine | Tilluftstryck |
| exhaust_pressure | Extract pressure | Poistopaine | Frånluftstryck |
| aux1_status | AUX1 status | AUX1-tila | AUX1-status |
| outlet_valve_control_status | Outlet valve control status | Ulospuhallusventtiilin tila | Utloppsventilens status |
| bypass_active | Bypass active | Ohitus päällä | Förbigång aktiv |
| speed | Fan speed | Nopeus | Fläkthastighet |
| force_control | Force control | Pakko-ohjaus | Tvångsstyrning |
| direct_control_enabled | Direct control enabled | Suoraohjaus käytössä | Direktstyrning aktiverad |
| supply_fan_direct_control | Supply fan direct control | Tulopuhaltimen suoraohjaus | Tilluftsfläkt direktstyrning |
| exhaust_fan_direct_control | Extract fan direct control | Poistopuhaltimen suoraohjaus | Frånluftsfläkt direktstyrning |
| temperature_setpoint | Temperature setpoint | Lämpötilan asetuspiste | Temperaturbörvärde |
| away_temperature_setpoint | Away temperature setpoint | Lämpötilan asetuspiste, poissa | Temperaturbörvärde borta |
| aux3_setpoint | AUX3 setpoint | AUX3-asetuspiste | AUX3-börvärde |
| aux4_setpoint | AUX4 setpoint | AUX4-asetuspiste | AUX4-börvärde |
| filter_change_interval | Filter change interval | Suodattimen vaihtoväli | Filterbytesintervall |
| constant_pressure_state | Constant pressure mode | Vakiopainesäätö | Konstanttrycksläge |
| home_away | Home/away | Kotona/poissa | Hemma/borta |
| cp_supply_speed1_setpoint … cp_supply_speed5_setpoint | Constant pressure supply setpoint 1…5 | VP tulo, nopeus 1…5 asetusarvo | Konstanttryck tilluft börvärde 1…5 |
| cp_exhaust_speed1_setpoint … cp_exhaust_speed5_setpoint | Constant pressure extract setpoint 1…5 | VP poisto, nopeus 1…5 asetusarvo | Konstanttryck frånluft börvärde 1…5 |
| cp_deviation_setpoint | Constant pressure deviation | VP poikkeama-asetusarvo | Konstanttrycksavvikelse |
| filter_guard_state | Filter guard mode | Suodatinvahdin tila | Filtervaktsläge |
| filter_guard_supply_ref | Filter guard supply reference | Suodatinvahti tulo, referenssi | Filtervakt tilluft referens |
| filter_guard_exhaust_ref | Filter guard extract reference | Suodatinvahti poisto, referenssi | Filtervakt frånluft referens |
| emergency_stop_resume | Emergency stop manual resume | Hätäseis, manuaalinen kuittaus | Nödstopp manuell återställning |
| transmitter_coefficient | Transmitter control coefficient | Lähetintoiminnon ohjauskerroin | Sändarfunktionens koefficient |
| transmitter_deviation | Transmitter deviation | Lähetintoiminnon poikkeama | Sändarfunktionens avvikelse |
| fire_hazard_supply_temp_limit | Fire hazard supply temperature limit | Palovaara, tulo lämpöraja | Brandrisk tilluft temperaturgräns |
| fire_hazard_exhaust_temp_limit | Fire hazard extract temperature limit | Palovaara, poisto lämpöraja | Brandrisk frånluft temperaturgräns |
| post_ventilation_time | Post-ventilation time | Jälkituuletusaika | Efterventilationstid |
| buzzer_mute | Buzzer mute | Summerin sammutus | Summer avstängd |
| filter_change_reminder | Filter change reminder | Suodattimen vaihtomuistutus | Filterbytespåminnelse |
| supply_fan_speed1_pct … supply_fan_speed5_pct | Supply fan speed 1…5 | Tulopuhallin nopeus 1…5 | Tilluftsfläkt hastighet 1…5 |
| exhaust_fan_speed1_pct … exhaust_fan_speed5_pct | Extract fan speed 1…5 | Poistopuhallin nopeus 1…5 | Frånluftsfläkt hastighet 1…5 |
| separate_supply_fan_values | Separate supply fan values | Erilliset tulopuhallinarvot | Separata tilluftsvärden |
| supply_fan_correction | Supply fan correction | Tulopuhaltimen korjaus | Tilluftsfläktens korrigering |
| bypass_set_temperature | Bypass set temperature | Ohituksen asetuslämpötila | Förbigångens börtemperatur |
| bypass_lower_limit | Bypass lower limit | Ohituksen sallittu alaraja | Förbigångens nedre gräns |
| bypass_delay | Bypass delay | Ohituksen viive | Förbigångens fördröjning |
| supply_air_minimum_temperature | Supply air minimum temperature | Tuloilman minimiasetus | Tilluftens minimitemperatur |
| enhanced_cooling_allowed | Enhanced cooling allowed | Tehostettu viilennys sallittu | Förstärkt kylning tillåten |
| cooling_temp_limit | Cooling temperature limit | Viilennyskäytön lämpötilaraja | Kyldriftens temperaturgräns |
| pre_heating_temp_limit | Pre-heating temperature limit | Esilämmityksen lämpötilaraja | Förvärmningens temperaturgräns |
| outdoor_valve_manual | Outdoor valve manual state | Ulkoventtiilin käsiohjaus | Uteventil manuellt läge |
| rh_sensor_mode | Internal RH sensor mode | Sisäisen kosteusanturin tila | Internt fuktsensorläge |
| sauna_mode | Sauna mode | Sauna | Bastuläge |
| fireplace_mode | Fireplace mode | Takka | Braskaminläge |
| heat_exchanger_disable | Rotary heat exchanger disable | Roottorin pysäytys | Rotor avstängd |
| co2_setpoint | CO2 setpoint | CO2-asetusarvo | CO2-börvärde |
| internal_co2_enabled | Internal CO2 sensor enabled | Sisäinen CO2-anturi käytössä | Intern CO2-sensor aktiverad |
| boost_time | Boost time | Tehostuksen kesto | Boost-tid |
| boost_speed_addition | Boost speed addition | Tehostuksen nopeuslisä | Boost-hastighetstillägg |
| boost_block | Boost block | Tehostuksen esto | Boost-blockering |
| aux1_control | AUX1 control | AUX1-ohjaus | AUX1-styrning |
| modbus_rh_sensor | External RH sensor (Modbus) | Modbus-kosteusanturi | Extern fuktsensor (Modbus) |
| modbus_co2_sensor | External CO2 sensor (Modbus) | Modbus-CO2-anturi | Extern CO2-sensor (Modbus) |
| modbus_temperature_sensor | External temperature sensor (Modbus) | Modbus-lämpötila-anturi | Extern temperatursensor (Modbus) |

Select option states (translate per language): `speed`: off/speed_1…speed_5 →
"Off/Speed 1…5", "Pois/Nopeus 1…5", "Av/Hastighet 1…5"; `force_control`:
disabled/mode_1…mode_3 → "Disabled/Mode 1…3", "Pois/Tila 1…3", "Av/Läge 1…3";
`filter_change_interval`: `1_month`…`6_months` → "1 month…6 months",
"1 kuukausi…6 kuukautta", "1 månad…6 månader"; `constant_pressure_state` and
`filter_guard_state`: off/supply_only/supply_and_exhaust → "Off/Supply only/
Supply and extract", "Pois/Vain tulo/Tulo ja poisto", "Av/Endast tilluft/
Tilluft och frånluft"; `home_away`: away/home → "Away/Home", "Poissa/Kotona",
"Borta/Hemma"; `rh_sensor_mode`: off/mode_1/mode_2 → "Off/Mode 1/Mode 2",
"Pois/Tila 1/Tila 2", "Av/Läge 1/Läge 2"; `boost_block`: none/block_1…block_4 →
"None/Block 1…4", "Ei estoa/Esto 1…4", "Ingen/Blockering 1…4".

The `config`/`options` sections get translated the same way (fi and sv versions
of the English strings shown in the structure above).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_translations.py -v` — Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/airfi/strings.json custom_components/airfi/translations tests/test_translations.py
git commit -m "Add English, Finnish, and Swedish translations

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 13: Device simulator (`tools/simulator.py`)

**Files:**
- Create: `tools/simulator.py`, `tools/__init__.py` (empty)
- Test: `tests/test_simulator.py`

**Interfaces:**
- Produces a standalone script: `uv run python tools/simulator.py [--port 5020] [--serial 12345678] [--device-type 1] [--announce/--no-announce]`. Also importable pieces used by the test: `RegisterStore`, `build_response(store: RegisterStore, request: bytes) -> bytes`.

- [ ] **Step 1: Write the failing tests**

`tests/test_simulator.py`:
```python
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
    response = build_response(store, _request(4, 3, 2))  # regs 4–5 (0-based 3)
    # header(7) + byte count(1) + 2 registers
    assert response[7] == 4  # byte count follows function echo... adjust: [6]=fn
    values = struct.unpack(">HH", response[9:13])
    assert values[0] == 215


def test_read_more_than_20_registers_is_error() -> None:
    store = RegisterStore()
    response = build_response(store, _request(4, 0, 21))
    assert response[7] == 0x84  # function | 0x80 → exception
    assert response[8] == 0x02  # illegal data address


def test_write_single_register() -> None:
    store = RegisterStore()
    response = build_response(store, _request(6, 4, 999))  # holding reg 5
    assert store.holding_registers[5] == 999
    # Echo response
    assert response[7:] == struct.pack(">BHH", 6, 4, 999)[0:]
```

Note: the byte-offset assertions above are indicative; when implementing, print
the actual response layout once and align the test offsets with the real MBAP
frame (`transaction(2) protocol(2) length(2) unit(1) function(1) ...`). The
semantics asserted (values round-trip, >20 → exception 2, write persists) are
the contract; fix offsets, not semantics.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_simulator.py -v` — Expected: FAIL (ImportError)

- [ ] **Step 3: Implement**

`tools/simulator.py` — a standalone asyncio script, stdlib only:

```python
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
    while True:
        sock.sendto(packet, (MULTICAST_GROUP, MULTICAST_PORT))
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
    if not args.no_announce:
        asyncio.ensure_future(
            announce_loop(args.port, args.serial, args.device_type)
        )
    async with tcp:
        await tcp.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
```

Create empty `tools/__init__.py` so tests can import it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_simulator.py -v` — Expected: PASS (after aligning
the indicative byte offsets in the test with the real frame layout)

- [ ] **Step 5: Run the whole suite and commit**

Run: `uv run pytest` — Expected: ALL PASS

```bash
git add tools tests/test_simulator.py
git commit -m "Add standalone Airfi device simulator

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 14: Replace the prototype and verify end-to-end

**Files:**
- Delete: `core/config/custom_components/airfi/` (directory)
- Create: symlink `core/config/custom_components/airfi` → `../../../custom_components/airfi`

- [ ] **Step 1: Swap the prototype for the new integration**

```bash
rm -rf core/config/custom_components/airfi
mkdir -p core/config/custom_components
ln -s ../../../custom_components/airfi core/config/custom_components/airfi
ls -la core/config/custom_components/
```
Expected: symlink pointing at the new component. (`core/` is untracked; nothing to commit for it.)

- [ ] **Step 2: Start the simulator**

```bash
uv run python tools/simulator.py --port 5020
```
(background it; note that announcements advertise the device but HA always connects on the configured Modbus port — for simulator testing use manual entry with port 5020, since discovery assumes port 502.)

- [ ] **Step 3: Run the dev Home Assistant**

Start HA from the `core/` checkout the same way it was run before (it has a
populated `config/`): typically `cd core && script/run-in-env hass -c config`
or the venv it was set up with (`core/build/` hints at prior use; check
`core/config/` mtimes). Then in the UI: Settings → Devices & Services → Add
integration → Airfi → manual entry `127.0.0.1:5020`.

Verify manually:
1. Entry is created; device page shows model/manufacturer.
2. Temperature sensors show scaled values (21.5 °C etc.); RPM sensors show raw.
3. Changing "Fan speed" select writes through (simulator prints the write).
4. Options → polling interval change reloads the entry.
5. Disabled-by-default config entities appear under "+N entities not shown"
   and can be enabled.
6. With a real Airfi unit on the network: discovery lists it with model and
   serial; adding it works on port 502; values look sane against the unit's
   own display; toggling home/away from HA is reflected on the device.

- [ ] **Step 4: Record results**

Fix anything found (each fix as its own small commit with a test where
feasible). When the checklist passes, update `Specification.md`'s "fill in
later" note if units/scales were corrected against the real device, and commit.

- [ ] **Step 5: Final commit**

```bash
git add -A ':!core' ':!.idea'
git status   # review before committing
git commit -m "Final adjustments from end-to-end verification

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-review notes

- Spec coverage: discovery (T4, T10), manual entry (T10), multi-device (config
  entries, T7), 20-register batches (T2, T5), single-client (T5 lock +
  connect-per-op), scan interval option (T10), renaming (HA built-in, no code),
  register table with scaling/units/translations (T3, T12), model names (T2),
  serial unique_id + IP updates (T10, T11), simulator + tests (T13, throughout),
  prototype deletion (T14). Climate deliberately absent per design.
- Deviation from HA core guidelines (documented in Global Constraints): scan
  interval is configurable because the user's specification requires it.
- Entity ids in platform tests assume object ids fall back to translation keys
  until Task 12 adds translations; after Task 12 they stay stable because
  object ids are fixed at first registration. If a test id mismatches, inspect
  with `hass.states.async_entity_ids()` and correct the id, never the value
  assertion.
