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
