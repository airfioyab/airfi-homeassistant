"""Constants for the Airfi integration."""

from __future__ import annotations

import logging

DOMAIN = "airfi"
LOGGER = logging.getLogger(__package__)

DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600
CONF_SCAN_INTERVAL = "scan_interval"
# Modbus unit/device id. The firmware drops frames addressed to any other id
# (except 0), and installations sometimes set it to e.g. a flat number.
CONF_MODBUS_ID = "modbus_id"
DEFAULT_MODBUS_ID = 1
MIN_MODBUS_ID = 1
MAX_MODBUS_ID = 247
CONF_SERIAL = "serial"
CONF_DEVICE_TYPE = "device_type"

# Modbus hardware constraints (see design spec).
MAX_REGISTERS_PER_READ = 20

# The register-layout version (input register 3, firmware MODBUS_VERSION)
# this integration's register tables were built against. A different value
# from the device is logged as a warning, not treated as fatal.
EXPECTED_MODBUS_REGISTER_VERSION = 360
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
# The base input batches work on every firmware; registers beyond 49 exist
# only from certain register versions on and are read as a gated extension
# (a batch touching a register unknown to the firmware fails whole).
INPUT_REGISTER_BATCHES: list[tuple[int, int]] = [(1, 20), (21, 20), (41, 9)]

# (minimum register version, extension batch) — newest first; the first
# entry whose version the device reaches is used.
# >= 350: 50 CO2 + 51/52 measured constant-pressure values; >= 340: 50 only.
INPUT_EXTENSION_BATCHES: list[tuple[int, tuple[int, int]]] = [
    (350, (50, 3)),
    (340, (50, 1)),
]
HOLDING_REGISTER_BATCHES: list[tuple[int, int]] = [
    (1, 20),
    (21, 20),
    (41, 20),
    (61, 8),
]

DEVICE_MODELS: dict[int, str] = {
    0: "Proto",
    1: "Model 60 L",
    2: "Model 60 R",
    3: "Model 100 L",
    4: "Model 100 R",
    7: "Model 130 L",
    8: "Model 130 R",
    5: "Model 150 L",
    6: "Model 150 R",
    9: "Model 250 L Electric",
    10: "Model 250 R Electric",
    11: "Model 250 L Water",
    12: "Model 250 R Water",
    13: "Model 350 L Electric",
    14: "Model 350 R Electric",
    15: "Model 350 L Water",
    16: "Model 350 R Water",
    17: "Model C5 L Electric",
    18: "Model C5 R Electric",
    19: "Model C5 L Water",
    20: "Model C5 R Water",
    21: "Model 53 mini L",
    22: "Model 53 mini R",
    23: "Model 53 miniEnt L",
    24: "Model 53 miniEnt R",
    25: "Model 60 Ent L",
    26: "Model 60 Ent R",
    27: "Model 130 Ent L",
    28: "Model 130 Ent R",
    29: "Model 150 Ent L",
    30: "Model 150 Ent R",
    31: "Model 250 EntL Electric",
    32: "Model 250 Ent R Electric",
    33: "Model 250 Ent L Water",
    34: "Model 250 Ent R Water",
    35: "Model 350 Ent L Electric",
    36: "Model 350 Ent R Electric",
    37: "Model 350 Ent L Water",
    38: "Model 350 Ent R Water",
    39: "Model ReFit 10 L",
    40: "Model ReFit 10 R",
}


def model_name(device_type: int) -> str:
    """Return the human readable model name for a device type id."""
    return DEVICE_MODELS.get(device_type, f"Airfi unit (type {device_type})")
