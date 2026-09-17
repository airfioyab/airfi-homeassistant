"""Register descriptor tables for the Airfi integration — the single source of truth."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)

from .const import REG_HOLDING, REG_INPUT

# ---------------------------------------------------------------------------
# Register definition dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class AirfiRegisterDescription:
    """Fields shared by every register descriptor.

    AirfiEntity consumes this base directly, so common entity behavior
    (naming, category, default enablement, icon) lives in one place.
    """

    address: int
    key: str
    entity_category: EntityCategory | None = None
    enabled_by_default: bool = True
    icon: str | None = None


@dataclass(frozen=True, kw_only=True)
class AirfiSensorRegister(AirfiRegisterDescription):
    """Read-only sensor register."""

    register_type: str = REG_INPUT
    scale: float = 1.0
    signed: bool = False
    # Firmware packs hw/sw versions into one register as
    # major*100 + minor*10 + patch (see modbus-handler.cpp).
    is_version: bool = False
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT


@dataclass(frozen=True, kw_only=True)
class AirfiBinarySensorRegister(AirfiRegisterDescription):
    """Read-only binary sensor register (or single bit within a register)."""

    register_type: str = REG_INPUT
    # If not None, this is bit N within the register (for bitmask registers).
    bit: int | None = None
    # True when the register's raw value is inverted relative to the
    # entity's meaning (e.g. home/away: raw 0 = home = sensor on).
    inverted: bool = False
    device_class: BinarySensorDeviceClass | None = None


@dataclass(frozen=True, kw_only=True)
class AirfiNumberRegister(AirfiRegisterDescription):
    """Writable numeric register (holding)."""

    min_value: float
    max_value: float
    scale: float = 1.0
    step: float = 1.0
    unit: str | None = None
    device_class: NumberDeviceClass | None = None
    mode: NumberMode = NumberMode.AUTO


@dataclass(frozen=True, kw_only=True)
class AirfiSelectRegister(AirfiRegisterDescription):
    """Writable select register (holding)."""

    # Ordered list of (raw_value, option_key) pairs.
    options: tuple[tuple[int, str], ...]


@dataclass(frozen=True, kw_only=True)
class AirfiSwitchRegister(AirfiRegisterDescription):
    """Writable on/off register (holding, 0=off 1=on)."""

    device_class: SwitchDeviceClass | None = None


@dataclass(frozen=True, kw_only=True)
class AirfiButtonRegister(AirfiRegisterDescription):
    """Write-only action register (holding): pressing writes press_value."""

    press_value: int = 0


# ---------------------------------------------------------------------------
# Input register definitions — read-only sensors
# ---------------------------------------------------------------------------

SENSOR_REGISTERS: tuple[AirfiSensorRegister, ...] = (
    # --- Version info (diagnostic) ---
    AirfiSensorRegister(
        address=1, key="hardware_version",
        unit=None, device_class=None, state_class=None, is_version=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AirfiSensorRegister(
        address=2, key="software_version",
        unit=None, device_class=None, state_class=None, is_version=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AirfiSensorRegister(
        address=3, key="modbus_register_version",
        unit=None, device_class=None, state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Temperatures T1–T6 (scale 0.1 → tenths of °C) ---
    AirfiSensorRegister(
        address=4, key="outdoor_air_temperature",
        scale=0.1, signed=True, unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AirfiSensorRegister(
        address=5, key="supply_air_temperature",
        scale=0.1, signed=True, unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AirfiSensorRegister(
        address=6, key="exhaust_air_temperature",
        scale=0.1, signed=True, unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AirfiSensorRegister(
        address=7, key="waste_air_temperature",
        scale=0.1, signed=True, unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AirfiSensorRegister(
        address=8, key="supply_air_apartment_temperature",
        scale=0.1, signed=True, unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AirfiSensorRegister(
        address=9, key="freeze_protection_temperature",
        scale=0.1, signed=True, unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    # --- Fan speeds and RPM ---
    AirfiSensorRegister(
        address=11, key="exhaust_fan_speed",
        unit=PERCENTAGE, icon="mdi:fan",
    ),
    AirfiSensorRegister(
        address=12, key="supply_fan_speed",
        unit=PERCENTAGE, icon="mdi:fan",
    ),
    AirfiSensorRegister(
        address=21, key="supply_fan_rpm",
        unit=REVOLUTIONS_PER_MINUTE, icon="mdi:fan",
    ),
    AirfiSensorRegister(
        address=22, key="exhaust_fan_rpm",
        unit=REVOLUTIONS_PER_MINUTE, icon="mdi:fan",
    ),
    AirfiSensorRegister(
        address=24, key="fan_speed_output",
        unit=PERCENTAGE, icon="mdi:fan",
    ),
    # --- Humidity ---
    AirfiSensorRegister(
        address=23, key="humidity",
        unit=PERCENTAGE, device_class=SensorDeviceClass.HUMIDITY,
    ),
    # --- Control state readbacks ---
    AirfiSensorRegister(
        address=25, key="force_control_state",
        unit=None, icon="mdi:tune",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AirfiSensorRegister(
        address=27, key="direct_control_percentage",
        unit=PERCENTAGE, icon="mdi:tune",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AirfiSensorRegister(
        address=28, key="temperature_setpoint_readback",
        scale=0.1, signed=True, unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AirfiSensorRegister(
        address=29, key="aux3_setpoint_readback",
        unit=None,
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
    AirfiSensorRegister(
        address=30, key="aux4_setpoint_readback",
        unit=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
    AirfiSensorRegister(
        address=31, key="filter_change_interval_readback",
        unit=None,
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
    # --- AUX values ---
    AirfiSensorRegister(
        address=13, key="aux3_mode",
        unit=None,
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
    AirfiSensorRegister(
        address=14, key="aux4_mode",
        unit=None,
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
    AirfiSensorRegister(
        address=33, key="aux3_read_value",
        unit=None,
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
    AirfiSensorRegister(
        address=34, key="aux4_read_value",
        unit=None,
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
    AirfiSensorRegister(
        address=38, key="aux2_state",
        unit=None,
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
    # --- Pressures ---
    AirfiSensorRegister(
        address=45, key="intake_pressure",
        unit=UnitOfPressure.PA, device_class=SensorDeviceClass.PRESSURE,
    ),
    AirfiSensorRegister(
        address=46, key="exhaust_pressure",
        unit=UnitOfPressure.PA, device_class=SensorDeviceClass.PRESSURE,
    ),
    # --- Misc ---
    AirfiSensorRegister(
        address=40, key="range_hood_compensation",
        unit=PERCENTAGE, icon="mdi:stove",
        enabled_by_default=False,
    ),
    AirfiSensorRegister(
        address=41, key="s1_read_value",
        unit=None,
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
    AirfiSensorRegister(
        address=42, key="room_sensor",
        scale=0.1, signed=True, unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        enabled_by_default=False,
    ),
    AirfiSensorRegister(
        address=43, key="post_heat_valve",
        unit=PERCENTAGE, icon="mdi:valve",
    ),
    AirfiSensorRegister(
        address=48, key="outlet_valve_control_status",
        unit=None, icon="mdi:valve",
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
)

# ---------------------------------------------------------------------------
# Binary sensor register definitions
# ---------------------------------------------------------------------------

BINARY_SENSOR_REGISTERS: tuple[AirfiBinarySensorRegister, ...] = (
    AirfiBinarySensorRegister(
        address=15, key="fireplace_active",
        icon="mdi:fireplace",
    ),
    AirfiBinarySensorRegister(
        address=16, key="home_away_state",
        # Firmware: 0 = home, 1 = away (modbus-handler.cpp, input reg 16).
        device_class=BinarySensorDeviceClass.PRESENCE, inverted=True,
        icon="mdi:home-account",
    ),
    AirfiBinarySensorRegister(
        address=17, key="emergency_stop",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AirfiBinarySensorRegister(
        address=18, key="freeze_alarm",
        device_class=BinarySensorDeviceClass.COLD,
    ),
    AirfiBinarySensorRegister(
        address=19, key="machine_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AirfiBinarySensorRegister(
        address=26, key="direct_control_active",
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
    AirfiBinarySensorRegister(
        address=35, key="constant_pressure_supply_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AirfiBinarySensorRegister(
        address=36, key="constant_pressure_exhaust_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AirfiBinarySensorRegister(
        # Holding register 34 reads v646: 1 = filter needs changing. It is
        # not writable as a toggle (the firmware only accepts 0 = reset,
        # exposed as a separate button entity).
        address=34, key="filter_change_due", register_type=REG_HOLDING,
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:air-filter",
    ),
    AirfiBinarySensorRegister(
        address=37, key="filter_guard_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    AirfiBinarySensorRegister(
        address=39, key="fire_alarm",
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    AirfiBinarySensorRegister(
        address=44, key="defrost_active",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    AirfiBinarySensorRegister(
        address=47, key="aux1_status",
        entity_category=EntityCategory.DIAGNOSTIC, enabled_by_default=False,
    ),
    AirfiBinarySensorRegister(
        address=49, key="bypass_active",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    # Error bitmask register 32 — bits E0–E8.
    # TODO: replace "error_eN" names with actual error descriptions once known.
    *[
        AirfiBinarySensorRegister(
            address=32,
            key=f"error_e{n}",
            bit=n,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        for n in range(9)
    ],
)

# ---------------------------------------------------------------------------
# Number register definitions — writable holding registers
# ---------------------------------------------------------------------------

NUMBER_REGISTERS: tuple[AirfiNumberRegister, ...] = (
    # Temperature setpoints (scale 0.1 — raw values are tenths of °C)
    AirfiNumberRegister(
        address=5, key="temperature_setpoint",
        min_value=17.0, max_value=26.0, scale=0.1, step=0.5,
        unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE,
    ),
    AirfiNumberRegister(
        address=52, key="away_temperature_setpoint",
        min_value=5.0, max_value=26.0, scale=0.1, step=0.5,
        unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE,
    ),
    # Direct / manual fan control
    AirfiNumberRegister(
        address=4, key="direct_control_percentage",
        min_value=0, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=10, key="supply_fan_direct_control",
        min_value=0, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=11, key="exhaust_fan_direct_control",
        min_value=0, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    # Boost
    AirfiNumberRegister(
        address=62, key="boost_time",
        min_value=0, max_value=120,
        unit=UnitOfTime.MINUTES, device_class=NumberDeviceClass.DURATION,
        icon="mdi:timer-outline",
    ),
    AirfiNumberRegister(
        address=63, key="boost_speed_addition",
        min_value=0, max_value=100, unit=PERCENTAGE,
        icon="mdi:fan-plus",
    ),
    # AUX setpoints
    AirfiNumberRegister(
        address=6, key="aux3_setpoint",
        min_value=0, max_value=2000,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=7, key="aux4_setpoint",
        min_value=0, max_value=100,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    # Constant pressure (VP) setpoints — supply speeds 1–5
    AirfiNumberRegister(
        address=13, key="cp_supply_speed1_setpoint",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=14, key="cp_supply_speed2_setpoint",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=15, key="cp_supply_speed3_setpoint",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=16, key="cp_supply_speed4_setpoint",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=17, key="cp_supply_speed5_setpoint",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    # Constant pressure — exhaust speeds 1–5
    AirfiNumberRegister(
        address=18, key="cp_exhaust_speed1_setpoint",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=19, key="cp_exhaust_speed2_setpoint",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=20, key="cp_exhaust_speed3_setpoint",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=21, key="cp_exhaust_speed4_setpoint",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=22, key="cp_exhaust_speed5_setpoint",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=23, key="cp_deviation_setpoint",
        min_value=5, max_value=300,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    # Filter guard reference points
    AirfiNumberRegister(
        address=25, key="filter_guard_supply_ref",
        min_value=5, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=26, key="filter_guard_exhaust_ref",
        min_value=5, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    # Transmitter function
    AirfiNumberRegister(
        address=28, key="transmitter_coefficient",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=29, key="transmitter_deviation",
        min_value=0, max_value=999,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    # Fire hazard temperature limits (whole °C, no scaling)
    AirfiNumberRegister(
        address=30, key="fire_hazard_supply_temp_limit",
        min_value=0, max_value=99,
        unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=31, key="fire_hazard_exhaust_temp_limit",
        min_value=0, max_value=99,
        unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    # Post-ventilation time
    AirfiNumberRegister(
        address=32, key="post_ventilation_time",
        min_value=0, max_value=10,
        unit=UnitOfTime.MINUTES, device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    # Fan speed percentages — supply 1–5 and exhaust 1–5
    AirfiNumberRegister(
        address=35, key="supply_fan_speed1_pct",
        min_value=25, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=36, key="supply_fan_speed2_pct",
        min_value=25, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=37, key="supply_fan_speed3_pct",
        min_value=25, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=38, key="supply_fan_speed4_pct",
        min_value=25, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=39, key="supply_fan_speed5_pct",
        min_value=25, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=40, key="exhaust_fan_speed1_pct",
        min_value=25, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=41, key="exhaust_fan_speed2_pct",
        min_value=25, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=42, key="exhaust_fan_speed3_pct",
        min_value=25, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=43, key="exhaust_fan_speed4_pct",
        min_value=25, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=44, key="exhaust_fan_speed5_pct",
        min_value=25, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=46, key="supply_fan_correction",
        min_value=1, max_value=199, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    # Bypass settings (whole °C)
    AirfiNumberRegister(
        address=47, key="bypass_set_temperature",
        min_value=15, max_value=30,
        unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=48, key="bypass_lower_limit",
        min_value=1, max_value=30,
        unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=49, key="bypass_delay",
        min_value=5, max_value=30,
        unit=UnitOfTime.MINUTES, device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=50, key="supply_air_minimum_temperature",
        min_value=10, max_value=25,
        unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=53, key="cooling_temp_limit",
        min_value=10, max_value=99,
        unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=54, key="pre_heating_temp_limit",
        min_value=2, max_value=99,
        unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    # CO2
    AirfiNumberRegister(
        address=60, key="co2_setpoint",
        min_value=0, max_value=10000,
        unit="ppm", device_class=NumberDeviceClass.CO2,
    ),
    # Modbus sensor inputs (external sensors written into the device)
    AirfiNumberRegister(
        address=66, key="modbus_rh_sensor",
        min_value=0, max_value=100, unit=PERCENTAGE,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=67, key="modbus_co2_sensor",
        min_value=0, max_value=10000, unit="ppm",
        device_class=NumberDeviceClass.CO2,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiNumberRegister(
        address=68, key="modbus_temperature_sensor",
        min_value=0, max_value=65535,
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
)

# ---------------------------------------------------------------------------
# Select register definitions — writable holding registers with discrete options
# ---------------------------------------------------------------------------

SELECT_REGISTERS: tuple[AirfiSelectRegister, ...] = (
    AirfiSelectRegister(
        address=1, key="speed",
        options=(
            (0, "off"),
            (1, "speed_1"),
            (2, "speed_2"),
            (3, "speed_3"),
            (4, "speed_4"),
            (5, "speed_5"),
        ),
        icon="mdi:fan",
    ),
    AirfiSelectRegister(
        address=2, key="force_control",
        # Firmware (modbus-handler.cpp case 2): 0 = off, 1 = emergency
        # stop, 2 = away; there is no mode 3.
        options=(
            (0, "disabled"),
            (1, "emergency_stop"),
            (2, "away"),
        ),
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
        icon="mdi:tune",
    ),
    AirfiSelectRegister(
        address=8, key="filter_change_interval",
        # Firmware: filter reminders per YEAR, 1-6 (input reg 31 comment
        # "muistutuskerrat per vuosi"), not an interval in months.
        options=(
            (1, "1_per_year"),
            (2, "2_per_year"),
            (3, "3_per_year"),
            (4, "4_per_year"),
            (5, "5_per_year"),
            (6, "6_per_year"),
        ),
        entity_category=EntityCategory.CONFIG,
        icon="mdi:air-filter",
    ),
    AirfiSelectRegister(
        address=9, key="bypass_mode",
        # Firmware (case 9, "LTO-kennon ohitus"): heat-recovery cell
        # bypass, not constant pressure as the spec table suggested.
        options=(
            (0, "off"),
            (1, "on_speeds_1_2"),
            (2, "on_speeds_1_5"),
        ),
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
        icon="mdi:valve",
    ),
    AirfiSelectRegister(
        address=12, key="home_away",
        # Firmware: 0 = home, 1 = away (modbus-handler.cpp, holding reg 12).
        options=(
            (0, "home"),
            (1, "away"),
        ),
        icon="mdi:home-account",
    ),
    AirfiSelectRegister(
        address=24, key="filter_guard_state",
        # Firmware (case 24): 0 = off, 1 = on, 2 = on + calibrate.
        options=(
            (0, "off"),
            (1, "on"),
            (2, "calibrate"),
        ),
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
        icon="mdi:air-filter",
    ),
    AirfiSelectRegister(
        address=56, key="rh_sensor_mode",
        # Firmware (case 56): 0 = switch mode, 1 = transmitter mode,
        # 2 = disabled.
        options=(
            (0, "switch"),
            (1, "transmitter"),
            (2, "disabled"),
        ),
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
        icon="mdi:water-percent",
    ),
    AirfiSelectRegister(
        address=64, key="boost_block",
        # Firmware (case 64): which boost sources are blocked.
        options=(
            (0, "off"),
            (1, "humidity"),
            (2, "co2"),
            (3, "humidity_co2"),
            (4, "all"),
        ),
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
        icon="mdi:fan-plus",
    ),
)

# ---------------------------------------------------------------------------
# Switch register definitions — writable boolean holding registers
# ---------------------------------------------------------------------------

SWITCH_REGISTERS: tuple[AirfiSwitchRegister, ...] = (
    AirfiSwitchRegister(
        address=3, key="direct_control_enabled",
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiSwitchRegister(
        address=27, key="emergency_stop_resume",
        # Can resume an emergency-stopped unit — installer level, opt-in.
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
        icon="mdi:alert-circle-outline",
    ),
    AirfiSwitchRegister(
        address=33, key="buzzer_mute",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:bell-off-outline",
    ),
    AirfiSwitchRegister(
        address=45, key="separate_supply_fan_values",
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
    AirfiSwitchRegister(
        address=51, key="enhanced_cooling_allowed",
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
        icon="mdi:snowflake",
    ),
    AirfiSwitchRegister(
        address=55, key="outdoor_valve_manual",
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
        icon="mdi:valve",
    ),
    AirfiSwitchRegister(
        address=57, key="sauna_mode",
        icon="mdi:sauna",
    ),
    AirfiSwitchRegister(
        address=58, key="fireplace_mode",
        icon="mdi:fireplace",
    ),
    AirfiSwitchRegister(
        address=59, key="heat_exchanger_disable",
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
        icon="mdi:heat-wave",
    ),
    AirfiSwitchRegister(
        address=61, key="internal_co2_enabled",
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
        icon="mdi:molecule-co2",
    ),
    AirfiSwitchRegister(
        address=65, key="aux1_control",
        entity_category=EntityCategory.CONFIG, enabled_by_default=False,
    ),
)


BUTTON_REGISTERS: tuple[AirfiButtonRegister, ...] = (
    AirfiButtonRegister(
        # Firmware (modbus-handler.cpp case 34) accepts only 0: acknowledge
        # and clear the filter change reminder.
        address=34, key="filter_reminder_reset", press_value=0,
        icon="mdi:air-filter",
    ),
)


def scaled_value(raw: int, scale: float, signed: bool = False) -> float | int:
    """Convert a raw 16-bit register value to its display value."""
    if signed and raw > 0x7FFF:
        raw -= 0x10000
    if scale == 1.0:
        return raw
    return round(raw * scale, 2)


def format_version(raw: int) -> str:
    """Decode a version register into "major.minor.patch".

    The firmware encodes versions as major*100 + minor*10 + patch
    (modbus-handler.cpp, input registers 1 and 2).
    """
    return f"{raw // 100}.{raw // 10 % 10}.{raw % 10}"
