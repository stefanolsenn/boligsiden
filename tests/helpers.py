"""Shared setup and polling helpers for integration tests."""

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.boligsiden.api import API_URL
from custom_components.boligsiden.const import DOMAIN, MAX_JITTER


async def async_setup_search(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Load a search and wait for its entities."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def async_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
    response: dict,
) -> None:
    """Serve a new response and advance time past the next poll."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, json=response)
    freezer.tick(
        MAX_JITTER
        + hass.config_entries.async_entries(DOMAIN)[0].runtime_data.update_interval
    )
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
