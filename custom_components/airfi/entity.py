"""Base entity for all Airfi platforms."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AirfiConfigEntry, AirfiCoordinator
from .registers import AirfiRegisterDescription


class AirfiEntity(CoordinatorEntity[AirfiCoordinator]):
    """Common base: device info, naming, unique id."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirfiCoordinator,
        description: AirfiRegisterDescription,
    ) -> None:
        """Initialize from a register descriptor's common fields."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        # The config-entry unique_id is reserved for duplicate detection and
        # may change (manual->serial upgrade), so registry identity uses the
        # immutable entry_id.
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_translation_key = description.key
        self._attr_device_info = coordinator.device_info
        self._attr_entity_category = description.entity_category
        self._attr_entity_registry_enabled_default = description.enabled_by_default
        if description.icon is not None:
            self._attr_icon = description.icon


@callback
def async_add_register_entities[DescT: AirfiRegisterDescription](
    entry: AirfiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    entity_cls: type[Entity],
    descriptions: tuple[DescT, ...],
) -> None:
    """Create one entity per descriptor — shared by every platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        entity_cls(coordinator, description) for description in descriptions
    )
