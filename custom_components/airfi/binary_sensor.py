"""Airfi binary sensor platform."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .entity import AirfiEntity, async_add_register_entities
from .registers import BINARY_SENSOR_REGISTERS, AirfiBinarySensorRegister


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for one Airfi device."""
    async_add_register_entities(
        entry, async_add_entities, AirfiBinarySensor, BINARY_SENSOR_REGISTERS
    )


class AirfiBinarySensor(AirfiEntity, BinarySensorEntity):
    """A binary sensor backed by a register or a bit within one."""

    def __init__(
        self, coordinator: AirfiCoordinator, description: AirfiBinarySensorRegister
    ) -> None:
        """Initialize from a register descriptor."""
        super().__init__(coordinator, description)
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
            value = bool(raw & (1 << desc.bit))
        else:
            value = raw != 0
        return not value if desc.inverted else value
