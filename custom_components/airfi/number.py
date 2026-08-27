"""Airfi number platform."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AirfiConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for one Airfi device."""
