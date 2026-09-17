"""Airfi button platform — write-only action registers."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .entity import AirfiEntity, async_add_register_entities
from .registers import BUTTON_REGISTERS, AirfiButtonRegister


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities for one Airfi device."""
    async_add_register_entities(
        entry, async_add_entities, AirfiButton, BUTTON_REGISTERS
    )


class AirfiButton(AirfiEntity, ButtonEntity):
    """An action register: pressing writes the descriptor's press value."""

    def __init__(
        self, coordinator: AirfiCoordinator, description: AirfiButtonRegister
    ) -> None:
        """Initialize from a register descriptor."""
        super().__init__(coordinator, description)
        self._description = description

    async def async_press(self) -> None:
        """Write the action value."""
        await self.coordinator.async_write_value(
            self._description.address, self._description.press_value
        )
