"""Base entity for all Airfi platforms."""

from __future__ import annotations

from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AirfiCoordinator


class AirfiEntity(CoordinatorEntity[AirfiCoordinator]):
    """Common base: device info, naming, unique id."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirfiCoordinator,
        key: str,
        entity_category: EntityCategory | None,
        enabled_by_default: bool,
        icon: str | None,
    ) -> None:
        """Initialize from a register descriptor's common fields."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        base = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = coordinator.device_info
        self._attr_entity_category = entity_category
        self._attr_entity_registry_enabled_default = enabled_by_default
        if icon is not None:
            self._attr_icon = icon
