"""Tests for the listing update event entity."""

from __future__ import annotations

import copy

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.boligsiden.api import API_URL
from custom_components.boligsiden.const import EVENT_NEW_LISTING

from .helpers import async_poll, async_setup_search

EVENT_ENTITY = "event.boligsiden_naestved_listing_update"


def _with_new_cases(response: dict, *case_ids: str) -> dict:
    updated = copy.deepcopy(response)
    for case_id in case_ids:
        updated["cases"].append(
            {**copy.deepcopy(response["cases"][0]), "caseID": case_id}
        )
    updated["totalHits"] = len(updated["cases"])
    return updated


async def test_event_entity_created(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
) -> None:
    """The event entity offers the three event types."""
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, config_entry)

    state = hass.states.get(EVENT_ENTITY)
    assert state is not None
    assert state.attributes["event_types"] == [
        "new_listing",
        "price_changed",
        "listing_removed",
    ]


async def test_event_received_trigger(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
) -> None:
    """The "Event received" trigger fires once per new listing."""
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, config_entry)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "triggers": [
                    {
                        "trigger": "event.received",
                        "target": {"entity_id": EVENT_ENTITY},
                        "options": {"event_type": ["new_listing"]},
                    }
                ],
                "actions": [
                    {
                        "event": "test_notified",
                        "event_data": {
                            "case_id": "{{ trigger.to_state.attributes.case_id }}",
                            "search": "{{ trigger.to_state.attributes.search }}",
                        },
                    }
                ],
                "mode": "queued",
            }
        },
    )
    notified = async_capture_events(hass, "test_notified")

    await async_poll(
        hass, freezer, aioclient_mock, _with_new_cases(search_response, "a", "b")
    )

    assert sorted(e.data["case_id"] for e in notified) == ["a", "b"]
    assert notified[0].data["search"] == "Næstved"
    state = hass.states.get(EVENT_ENTITY)
    assert state.attributes["event_type"] == "new_listing"
    assert state.attributes["case_id"] == "b"


async def test_events_wait_for_startup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
) -> None:
    """Changes found while Home Assistant starts are fired once it has started."""
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, config_entry)
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    events = async_capture_events(hass, EVENT_NEW_LISTING)
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, json=_with_new_cases(search_response, "new-case"))
    hass.set_state(CoreState.starting)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert events == []

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert [e.data["case_id"] for e in events] == ["new-case"]
    assert hass.states.get(EVENT_ENTITY).attributes["case_id"] == "new-case"
