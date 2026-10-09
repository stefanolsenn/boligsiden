"""The Boligsiden integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.start import async_at_started

from .api import BoligsidenClient
from .coordinator import BoligsidenCoordinator, listing_store

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.SENSOR]

type BoligsidenConfigEntry = ConfigEntry[BoligsidenCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BoligsidenConfigEntry) -> bool:
    """Set up a Boligsiden search from a config entry."""
    client = BoligsidenClient(async_get_clientsession(hass))
    coordinator = BoligsidenCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Changes found by the first poll are fired once Home Assistant has started,
    # so automations and the event entity are listening.
    entry.async_on_unload(async_at_started(hass, coordinator.async_start_events))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BoligsidenConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: BoligsidenConfigEntry) -> None:
    """Delete the stored listings when a search is removed."""
    await listing_store(hass, entry.entry_id).async_remove()
