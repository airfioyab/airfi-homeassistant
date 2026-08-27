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
