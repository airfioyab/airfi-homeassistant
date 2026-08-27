"""Airfi sensor platform."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .entity import AirfiEntity
from .registers import (
    SENSOR_REGISTERS,
    AirfiSensorRegister,
    format_version,
    scaled_value,
)


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
    def native_value(self) -> float | int | str | None:
        """Scaled register value, or a decoded version string."""
        desc = self._description
        raw = self.coordinator.data[desc.register_type].get(desc.address)
        if raw is None:
            return None
        if desc.is_version:
            return format_version(raw)
        return scaled_value(raw, desc.scale, desc.signed)
