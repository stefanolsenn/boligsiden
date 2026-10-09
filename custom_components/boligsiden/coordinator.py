"""Coordinator that polls Boligsiden and detects listing changes."""

from __future__ import annotations

import random
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BoligsidenClient, BoligsidenError, Listing
from .const import (
    CONF_CITY,
    CONF_PRICE_MAX,
    CONF_PRICE_MIN,
    CONF_PROPERTY_TYPES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_LISTING_REMOVED,
    EVENT_NEW_LISTING,
    EVENT_PRICE_CHANGED,
    LOGGER,
    MAX_JITTER,
    PROPERTY_TYPES,
    STORAGE_VERSION,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import BoligsidenConfigEntry


def listing_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Return the store holding the listings last seen for a config entry."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")


class BoligsidenCoordinator(DataUpdateCoordinator[dict[str, Listing]]):
    """Fetch listings for one saved search and fire events on changes."""

    config_entry: BoligsidenConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BoligsidenConfigEntry,
        client: BoligsidenClient,
    ) -> None:
        """Initialize the coordinator."""
        interval = timedelta(
            minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        jitter = timedelta(seconds=random.randint(0, int(MAX_JITTER.total_seconds())))
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=interval + jitter,
        )
        self.client = client
        self._store = listing_store(hass, entry.entry_id)
        # Listings from the previous poll, keyed by case ID. None until loaded.
        self._known: dict[str, dict[str, Any]] | None = None
        # Events found before Home Assistant has started and the entities exist.
        # The first poll runs during setup, when automations and the event entity
        # may not listen yet. None once events are fired directly.
        self._pending_events: list[tuple[str, dict[str, Any]]] | None = []

    @callback
    def async_start_events(self, _: Any = None) -> None:
        """Fire the events queued during setup, and fire directly from now on."""
        pending, self._pending_events = self._pending_events or [], None
        for event_type, data in pending:
            self.hass.bus.async_fire(event_type, data)

    def _fire(self, event_type: str, data: dict[str, Any]) -> None:
        """Fire an event, or queue it until async_start_events is called."""
        if self._pending_events is not None:
            self._pending_events.append((event_type, data))
        else:
            self.hass.bus.async_fire(event_type, data)

    async def _async_setup(self) -> None:
        """Load listings seen before the last restart."""
        stored = await self._store.async_load()
        if stored is not None:
            self._known = stored.get("listings", {})

    async def _async_update_data(self) -> dict[str, Listing]:
        """Fetch listings and fire events for what changed."""
        entry = self.config_entry
        try:
            listings = await self.client.async_search(
                city=entry.data[CONF_CITY],
                property_types=[
                    PROPERTY_TYPES[key] for key in entry.data[CONF_PROPERTY_TYPES]
                ],
                price_min=entry.options.get(CONF_PRICE_MIN),
                price_max=entry.options.get(CONF_PRICE_MAX),
            )
        except BoligsidenError as err:
            raise UpdateFailed(str(err)) from err

        current = {listing.case_id: listing for listing in listings}

        if self._known is None:
            # First run for this search. Record what's there without firing
            # events, so setting up the integration doesn't send a push per listing.
            LOGGER.debug("Seeding %s with %d listings", entry.title, len(current))
        else:
            self._fire_events(self._known, current)

        self._known = {case_id: l.as_dict() for case_id, l in current.items()}
        await self._store.async_save({"listings": self._known})
        return current

    def _fire_events(
        self, previous: dict[str, dict[str, Any]], current: dict[str, Listing]
    ) -> None:
        """Fire an event for every new, repriced and removed listing."""
        base = {
            "entry_id": self.config_entry.entry_id,
            "search": self.config_entry.title,
        }

        for case_id, listing in current.items():
            old = previous.get(case_id)
            if old is None:
                self._fire(EVENT_NEW_LISTING, {**base, **listing.as_dict()})
            elif (
                old.get("price") is not None
                and listing.price is not None
                and old["price"] != listing.price
            ):
                self._fire(
                    EVENT_PRICE_CHANGED,
                    {
                        **base,
                        **listing.as_dict(),
                        "old_price": old["price"],
                        "price_difference": listing.price - old["price"],
                    },
                )

        for case_id, old in previous.items():
            if case_id not in current:
                self._fire(EVENT_LISTING_REMOVED, {**base, **old})
