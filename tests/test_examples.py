"""Render the templates in examples/ so the docs keep working."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.boligsiden.api import API_URL

from .helpers import async_poll, async_setup_search

EXAMPLES = Path(__file__).parent.parent / "examples"


def _walk_cards(node):
    """Yield the dictionaries nested in a dashboard config."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_cards(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_cards(value)


@pytest.mark.parametrize("with_listings", [True, False])
async def test_dashboard_renders(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
    with_listings: bool,
) -> None:
    """Every markdown card renders, with and without listings."""
    if not with_listings:
        search_response = {"cases": None, "totalHits": 0}
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, config_entry)

    dashboard = yaml.safe_load((EXAMPLES / "dashboard.yaml").read_text())
    entities = {card["entity"] for card in _walk_cards(dashboard) if "entity" in card}
    for entity_id in entities:
        assert hass.states.get(entity_id), f"{entity_id} does not exist"

    cards = [card for card in _walk_cards(dashboard) if card.get("type") == "markdown"]
    assert len(cards) == 4
    rendered_cards = [
        Template(card["content"], hass).async_render(parse_result=False)
        for card in cards
    ]
    budget = next(r for r in rendered_cards if "between 2.000.000 and 3.500.000" in r)
    others = [r for r in rendered_cards if r is not budget]

    if with_listings:
        for rendered in others:
            assert "Eksempelvej 25" in rendered or "Demovej 52" in rendered
            assert "kr." in rendered
        # 2.698.000 and 3.395.000 are in the budget, 675.000 is not.
        assert "**2 homes**" in budget
        assert "Eksempelvej 25" in budget
        assert "Prøvevej 26" in budget
        assert "Demovej 52" not in budget
    else:
        for rendered in others:
            assert "No listings right now." in rendered
        assert "**0 homes**" in budget
        assert "| Address |" not in budget


async def test_automations_notify(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
) -> None:
    """The example automations send the expected notifications."""
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, config_entry)

    automations = yaml.safe_load((EXAMPLES / "automations.yaml").read_text())
    assert len(automations) == 3
    assert await async_setup_component(hass, "automation", {"automation": automations})
    calls = async_mock_service(hass, "notify", "mobile_app_your_phone")

    # Demovej 52 is removed, Prøvevej 26 drops 100.000 kr. and a
    # copy of Eksempelvej 25 is added as a new listing.
    updated = copy.deepcopy(search_response)
    removed = updated["cases"].pop(2)
    updated["cases"][1]["priceCash"] -= 100_000
    updated["cases"].append({**copy.deepcopy(updated["cases"][0]), "caseID": "new"})
    await async_poll(hass, freezer, aioclient_mock, updated)

    sent = {call.data["title"]: call.data for call in calls}
    assert set(sent) == {
        "New in Næstved: Eksempelvej 25",
        "Price drop: Prøvevej 26",
        "Gone: Demovej 52",
    }
    new = sent["New in Næstved: Eksempelvej 25"]
    assert new["message"] == "2.698.000 kr. · 148 m² · 5 rooms · Eksempel Mægler"
    assert new["data"]["tag"] == "new"
    assert new["data"]["image"].startswith("https://images.boligsiden.dk/")
    assert new["data"]["url"] == new["data"]["clickAction"]
    assert (
        sent["Price drop: Prøvevej 26"]["message"]
        == "3.395.000 kr. → 3.295.000 kr. (100.000 kr. less)"
    )
    assert sent["Gone: Demovej 52"]["message"] == (
        f"Last price 675.000 kr. after {removed['daysListed']['days']} days on the market."
    )

    # A price increase doesn't notify.
    calls.clear()
    updated["cases"][1]["priceCash"] += 200_000
    await async_poll(hass, freezer, aioclient_mock, updated)
    assert calls == []


async def test_manual_state_triggers_automation(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
) -> None:
    """Setting the event entity's state by hand, as the README suggests, notifies."""
    aioclient_mock.get(API_URL, json=search_response)
    await async_setup_search(hass, config_entry)
    automations = yaml.safe_load((EXAMPLES / "automations.yaml").read_text())
    assert await async_setup_component(hass, "automation", {"automation": automations})
    calls = async_mock_service(hass, "notify", "mobile_app_your_phone")

    hass.states.async_set(
        "event.boligsiden_naestved_listing_update",
        "test-1",
        {
            "event_type": "new_listing",
            "city": "Næstved",
            "address": "Testvej 1",
            "price": 2495000,
            "living_area": 140,
            "rooms": 5,
            "realtor": "Test Mægler",
            "case_id": "test",
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["title"] == "New in Næstved: Testvej 1"
    assert calls[0].data["message"] == "2.495.000 kr. · 140 m² · 5 rooms · Test Mægler"
