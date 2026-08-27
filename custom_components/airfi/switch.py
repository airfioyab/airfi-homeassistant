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
