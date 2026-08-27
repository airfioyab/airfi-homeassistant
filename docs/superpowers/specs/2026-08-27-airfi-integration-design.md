# Airfi Home Assistant Integration — Design

Date: 2026-08-27
Status: approved design, pending implementation plan

## Goal

A Home Assistant integration (`airfi`) for Airfi air handling units, communicating over
Modbus TCP, with automatic device discovery via the units' UDP multicast announcements.
Supports multiple units per household. Built as a custom component
(`custom_components/airfi/`) to HA core quality standards so it can later be submitted
upstream with minimal rework.

A previous prototype exists at `core/config/custom_components/airfi/`. Its register
table, batching, and flow skeleton are sound and are carried over; it will be deleted
and replaced by the new implementation. Differences from the prototype are listed at
the end of this document.

## Device facts (verified against firmware in `../airfi-sw/`)

- **Announcements**: every few seconds each unit multicasts a 15-byte packet to
  `239.255.100.200:3000` (`sendAnnouncement()` in `functions/network/network-udp.cpp`).
  Layout, little-endian (`struct` format `<IHIBI`):
  | Offset | Size | Field |
  |---|---|---|
  | 0 | 4 | IP address (uint32) |
  | 4 | 2 | UDP port for Airfi's proprietary protocol (**not** Modbus; currently 4000) |
  | 6 | 4 | Serial number |
  | 10 | 1 | Protocol version (currently 1) |
  | 11 | 4 | Device type ID |
- The parser uses the **packet source address** as the device IP and ignores the
  embedded IP field (endianness-fragile, and the source address is always right).
- **Modbus TCP** is on fixed port **502** (`functions/modbus/modbus-tcp.cpp`).
- At most **20 registers per read**; larger reads return a Modbus error.
- Only **one Modbus TCP client** may be connected at a time.
- Device type ID maps to human-readable model names; the canonical map is
  `FanData.models` in `tools/fan_data.py` (0="Proto", 1="Model 60 L" …
  38="Model 350 Ent R Water"), matching the `DeviceType` enum in
  `resources/constants.h`. The integration copies this map verbatim into
  `const.py`; unknown IDs fall back to "Airfi unit (type <id>)".
- Input registers 1–49 (register 10 unused), holding registers 1–68, all 16-bit.
  Spec register numbers are 1-based; pymodbus addressing is 0-based, so the wire
  address is `register - 1` (verify against `modbus-handler.cpp` during
  implementation).

## Architecture

Custom component at `custom_components/airfi/`. Only external dependency: `pymodbus`.
The full HA checkout in `core/` is the dev environment; the dev instance's
`config/custom_components/airfi` becomes a symlink to the component.

| Module | Responsibility |
|---|---|
| `registers.py` | Declarative table of all register descriptors — the single source of truth |
| `discovery.py` | Async multicast listener; parses announcements into `DiscoveredDevice(ip, serial, sw_version, device_type)` |
| `modbus.py` | Async pymodbus wrapper: connect → batched reads / single write → disconnect, serialized behind a per-device `asyncio.Lock` |
| `coordinator.py` | One `DataUpdateCoordinator` per device; produces `{"input": {addr: raw}, "holding": {addr: raw}}` |
| `config_flow.py` | Discovery + manual setup, options flow |
| `sensor.py`, `binary_sensor.py`, `number.py`, `select.py`, `switch.py` | One generic entity class per platform, driven entirely by descriptors |
| `entity.py` | Shared base entity (device info, availability) |
| `const.py` | Domain, defaults, protocol constants, device-type → model-name map |
| `manifest.json`, `strings.json`, `translations/{en,fi,sv}.json` | Metadata and translated names |

## Register descriptor model

Per-platform frozen dataclasses (as in the prototype): `AirfiSensorRegister`,
`AirfiBinarySensorRegister` (with optional `bit` for bitmask registers),
`AirfiNumberRegister`, `AirfiSelectRegister`, `AirfiSwitchRegister`. Common fields:
1-based register address, translation `key`, `scale` (default 1, raw→display
multiplier), unit, device class, `entity_category`, `enabled_by_default`, icon.
Numbers add min/max/step (from the spec's holding-register table); selects carry
ordered `(raw_value, option_key)` pairs.

Changing how a register is represented (e.g. sensor → switch) is a one-line move of
its descriptor between tables. Register names live in `translations/` keyed by `key`
(Finnish source names from the spec, English and Swedish translations).

Initial unit/scale guesses (carried from the prototype, refined against the real
unit later): temperatures ×0.1 °C (setpoint raw 170–260 → 17.0–26.0 °C), fan
speeds/percentages %, fan RPM, pressures Pa, CO2 ppm, durations min; unclear
registers get no unit and scale 1.

### Entity tiering

- **Enabled, primary**: temperatures T1–T6, fan speed %/RPM, humidity, pressures,
  post-heat valve; controls: speed (select 0–5), home/away (select), temperature
  setpoint, boost time/speed, CO2 setpoint, sauna/fireplace switches.
- **Binary sensors** for states and alarms: fireplace, home/away state, emergency
  stop, freeze alarm, machine fault, filter guard, fire alarm, defrost, bypass,
  constant-pressure alarms; E0–E8 as nine bit-mapped `PROBLEM` binary sensors.
- **Diagnostic category**: hw/sw/register versions, control readbacks, AUX values.
- **Config category, disabled by default**: fan curve percentages, constant-pressure
  setpoints, filter guard references, fire hazard limits, transmitter settings,
  bypass tuning, direct control, external Modbus sensor inputs, and other
  installer-level registers.

## Discovery and config flow

- `async_step_user` shows a menu: **discover** or **manual**.
- Discover: listen on the multicast group for ~8 s (progress UI), list devices as
  "Airfi <model> (SN <serial>) — <ip>", excluding already-configured serials.
  Selecting one creates the entry with `unique_id = serial`.
- Manual: host + port (default 502) + optional name; validated by reading input
  register 1. Since Modbus exposes no serial, manual entries use `host:port` as
  `unique_id`.
- If a discovery announcement later arrives for a configured serial with a new IP,
  the entry's host is updated automatically. An announcement matching a manual
  entry's host upgrades that entry's `unique_id` to the serial.
- Entry data: host, port, serial (when known), device type. Options flow: scan
  interval in seconds (default 30, min 5, max 3600). Renaming devices uses HA's
  built-in rename.
- Each device is its own config entry; multiple units are just multiple entries.

## Polling and writes

Each poll cycle, under the device lock: connect (≈5 s timeout) → read input
registers in batches (1–20, 21–40, 41–49) → read holding registers in batches
(1–20, 21–40, 41–60, 61–68) → disconnect. The unit is free for other Modbus
clients between polls.

Writes: under the same lock, connect → `write_register` → disconnect, optimistic
cache update, then an immediate coordinator refresh. Display values are converted
back to raw (inverse scale, rounded) and clamped to the descriptor's min/max.

Failures (refused connection because another client is attached, timeout, Modbus
exception) raise `UpdateFailed`; entities go unavailable and the next cycle
retries. Failed writes raise `HomeAssistantError` so the UI shows the error.

## Device registry

`identifiers = {(DOMAIN, entry_id)}` — the immutable config-entry id, because
the config-entry unique_id (the serial, or "host:port" for manual entries) is
reserved for duplicate detection and rediscovery and may change on the
manual→serial upgrade. Manufacturer "Airfi", model from the device-type map,
hw/sw versions from input registers 1–2, `configuration_url` = `http://<host>`.

## Simulator and testing

- `tools/simulator.py`: standalone asyncio script emulating a unit — multicast
  announcements plus a Modbus TCP server enforcing the 20-register limit and
  single-client behavior; configurable serial, device type, port, and register
  seed values. Used for manual development without hardware.
- Automated tests with `pytest` + `pytest-homeassistant-custom-component`:
  announcement parsing (valid/truncated/garbage), config flow paths (discover,
  manual, dedupe, options), coordinator batching and failure handling,
  write scaling/clamping, and representative entity mappings.
- Final verification against a real Airfi unit on the local network.

## Changes relative to the prototype

1. `unique_id` is the announcement serial, not `host:port` (prototype discarded
   the parsed serial); manual entries keep `host:port` until upgraded.
2. Connect-per-poll instead of a persistent connection, with an `asyncio.Lock`
   preventing write/poll races (prototype had no lock).
3. Real model names from the `DeviceType` enum instead of "Air Handling Unit".
4. No `climate.py` — raw entities only, per design decision.
5. IP taken from the packet source address, not the payload field.
6. Added: separate `discovery.py`, Swedish translations, simulator, tests,
   IP-update-on-rediscovery.
