"""Tests for setup, sensors and change events."""

from __future__ import annotations

import copy
from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.boligsiden.api import API_URL
from custom_components.boligsiden.const import (
    DOMAIN,
    EVENT_LISTING_REMOVED,
    EVENT_NEW_LISTING,
    EVENT_PRICE_CHANGED,
    MAX_JITTER,
)
from custom_components.boligsiden.diagnostics import async_get_config_entry_diagnostics

from .helpers import async_poll, async_setup_search

LISTINGS = "sensor.boligsiden_naestved_listings"


async def test_setup_creates_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
) -> None:
    """Setup creates the summary sensors."""
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get(LISTINGS)
    assert state.state == "3"
    assert len(state.attributes["listings"]) == 3
    days = [l["days_listed"] for l in state.attributes["listings"]]
    assert days == sorted(days)

    assert hass.states.get("sensor.boligsiden_naestved_lowest_price").state == str(
        min(c["priceCash"] for c in search_response["cases"])
    )
    newest = min(search_response["cases"], key=lambda c: c["daysListed"]["days"])
    assert hass.states.get("sensor.boligsiden_naestved_newest_listing").state == (
        f"{newest['address']['roadName']} {newest['address']['houseNumber']}"
    )
    assert (
        hass.states.get("sensor.boligsiden_naestved_average_price_per_m2") is not None
    )

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_on_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Setup is retried when the API is down."""
    aioclient_mock.get(API_URL, status=503)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_first_run_fires_no_events(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
) -> None:
    """Existing listings are recorded without events on first setup."""
    events = async_capture_events(hass, EVENT_NEW_LISTING)
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, config_entry)

    assert events == []


async def test_change_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
) -> None:
    """New, repriced and removed listings each fire an event."""
    new_events = async_capture_events(hass, EVENT_NEW_LISTING)
    price_events = async_capture_events(hass, EVENT_PRICE_CHANGED)
    removed_events = async_capture_events(hass, EVENT_LISTING_REMOVED)
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, config_entry)

    updated = copy.deepcopy(search_response)
    removed = updated["cases"].pop(2)
    repriced = updated["cases"][1]
    old_price = repriced["priceCash"]
    repriced["priceCash"] = old_price - 100_000
    added = {**copy.deepcopy(updated["cases"][0]), "caseID": "new-case"}
    updated["cases"].append(added)
    updated["totalHits"] = 3

    await async_poll(hass, freezer, aioclient_mock, updated)

    assert len(new_events) == 1
    assert new_events[0].data["case_id"] == "new-case"
    assert new_events[0].data["search"] == "Næstved"
    assert new_events[0].data["entry_id"] == config_entry.entry_id

    assert len(price_events) == 1
    assert price_events[0].data["case_id"] == repriced["caseID"]
    assert price_events[0].data["old_price"] == old_price
    assert price_events[0].data["price_difference"] == -100_000

    assert len(removed_events) == 1
    assert removed_events[0].data["case_id"] == removed["caseID"]

    # Nothing changed on the next poll, so no new events.
    await async_poll(hass, freezer, aioclient_mock, updated)
    assert (len(new_events), len(price_events), len(removed_events)) == (1, 1, 1)


async def test_known_listings_survive_restart(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
) -> None:
    """After a reload, only listings unseen before the reload are new."""
    events = async_capture_events(hass, EVENT_NEW_LISTING)
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, config_entry)
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    updated = copy.deepcopy(search_response)
    updated["cases"].append(
        {**copy.deepcopy(updated["cases"][0]), "caseID": "new-case"}
    )
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, json=updated)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert [e.data["case_id"] for e in events] == ["new-case"]


async def test_diagnostics(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
) -> None:
    """Diagnostics include the listings and a raw API case."""
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, config_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert diagnostics["listing_count"] == 3
    assert (
        diagnostics["last_raw_case"]["caseID"] == search_response["cases"][0]["caseID"]
    )


async def test_property_types_sent_as_api_values(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, search_response
) -> None:
    """Property type keys are mapped to the values the API expects."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Næstved",
        data={"city": "Næstved", "property_types": ["terraced_house", "villa"]},
    )
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, entry)

    params = aioclient_mock.mock_calls[0][1].query
    assert params["addressTypes"] == "terraced house,villa"


async def test_scan_interval_from_options(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, search_response
) -> None:
    """The poll interval comes from the options, plus up to MAX_JITTER."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Næstved",
        data={"city": "Næstved", "property_types": ["villa"]},
        options={"scan_interval": 60},
    )
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, entry)

    interval = entry.runtime_data.update_interval
    assert timedelta(minutes=60) <= interval <= timedelta(minutes=60) + MAX_JITTER
