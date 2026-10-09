"""Expose a search's bus events through the Listing update entity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.event import EventEntity
from homeassistant.core import Event, callback

from .const import EVENT_LISTING_REMOVED, EVENT_NEW_LISTING, EVENT_PRICE_CHANGED
from .entity import search_device_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import BoligsidenConfigEntry

# Bus event -> event type on the entity.
EVENT_TYPES = {
    EVENT_NEW_LISTING: "new_listing",
    EVENT_PRICE_CHANGED: "price_changed",
    EVENT_LISTING_REMOVED: "listing_removed",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoligsidenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event entity for a search."""
    async_add_entities([BoligsidenListingEvent(entry)])


class BoligsidenListingEvent(EventEntity):
    """Receives an event for every new, repriced and removed listing."""

    _attr_has_entity_name = True
    _attr_translation_key = "listing_update"

    def __init__(self, entry: BoligsidenConfigEntry) -> None:
        """Initialize the event entity."""
        self._entry_id = entry.entry_id
        self._attr_event_types = list(EVENT_TYPES.values())
        self._attr_unique_id = f"{entry.entry_id}_listing_update"
        self._attr_device_info = search_device_info(entry)

    async def async_added_to_hass(self) -> None:
        """Listen for the bus events of this search."""
        await super().async_added_to_hass()
        for bus_event in EVENT_TYPES:
            self.async_on_remove(
                self.hass.bus.async_listen(
                    bus_event,
                    self._async_handle_event,
                    event_filter=self._async_is_own_search,
                )
            )

    @callback
    def _async_is_own_search(self, event_data: Any) -> bool:
        """Return if a bus event belongs to this search."""
        return event_data.get("entry_id") == self._entry_id

    @callback
    def _async_handle_event(self, event: Event) -> None:
        """Trigger the entity with the listing as attributes."""
        self._trigger_event(EVENT_TYPES[event.event_type], dict(event.data))
        self.async_write_ha_state()
