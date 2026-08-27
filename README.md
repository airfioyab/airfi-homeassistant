# Airfi for Home Assistant

A custom Home Assistant integration for [Airfi](https://airfi.fi) air handling
units. It talks to the unit locally over Modbus TCP (no cloud) and finds
devices on the network via the units' UDP multicast announcements
(`239.255.100.200:3000`).

## Requirements

- Home Assistant 2025.x or newer (Python 3.13 based).
- The Airfi unit and Home Assistant on the same LAN, with the unit's Modbus
  TCP port (default 502) reachable. Automatic discovery additionally needs
  multicast traffic to pass between the unit and the Home Assistant host
  (same subnet, or a multicast-capable route).

## Installation

### Manual

1. Copy the `custom_components/airfi` directory into the `custom_components`
   folder of your Home Assistant configuration directory (create the folder
   if it does not exist).
2. Restart Home Assistant.

### HACS

The integration is not yet in the HACS default store. Once this repository
has a public home you can add it in HACS as a *custom repository*
(type: Integration) and install it from there.

> The `documentation` and `codeowners` fields in `manifest.json`, and an
> issue tracker link, will be filled in when the repository gets its public
> home.

## Configuration

Add the integration via **Settings → Devices & Services → Add Integration →
Airfi**. Two paths are offered:

- **Discovery**: listens a few seconds for unit announcements and lets you
  pick a found device. Devices that are already configured (by serial or by
  IP) are not offered again.
- **Manual**: enter the unit's host/IP and Modbus TCP port (default 502).
  A manual entry is automatically upgraded with the unit's serial number
  when an announcement from that IP is later received.

If a configured unit changes IP (DHCP), the integration picks up the new
address automatically from the announcements.

**Options** (per entry): polling interval in seconds (default 30,
range 5–3600).

## Entities

Entities come in two tiers:

- **Enabled by default**: the everyday values and controls — temperatures,
  fan speeds and RPM, humidity, fan speed selection, temperature setpoint,
  sauna/fireplace/boost modes, error indicators.
- **Disabled by default** (entity category *config/diagnostic*): installer
  and commissioning settings exposed by the unit's holding registers. Enable
  them per entity if you need them; changing them affects how the unit runs.

## Device simulator

`tools/simulator.py` emulates a unit for development without hardware:
multicast announcements plus a Modbus TCP server with realistic quirks
(max 20 registers per read, a single TCP client at a time).

```bash
uv run python tools/simulator.py [--port 5020] [--serial 12345678] \
    [--device-type 1] [--no-announce]
```

Point a manual config entry at `localhost` with the chosen port to test the
full integration against it.

## Development

```bash
uv sync                                      # install dependencies
uv run pytest                                # run the test suite
uv run ruff check custom_components tests tools  # lint
```

Tests use `pytest-homeassistant-custom-component`; no hardware or network
access is needed.
