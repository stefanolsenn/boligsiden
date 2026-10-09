"""Tests for the Boligsiden API client."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.boligsiden.api import (
    API_URL,
    PAGE_SIZE,
    BoligsidenClient,
    BoligsidenConnectionError,
    BoligsidenResponseError,
)

EMPTY = {"cases": None, "totalHits": 0}


async def test_search_parses_listings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, search_response
) -> None:
    """Listings are parsed from the raw response."""
    aioclient_mock.get(API_URL, json=search_response)
    client = BoligsidenClient(async_get_clientsession(hass))

    listings = await client.async_search("Næstved", ["villa"], price_min=1_000_000)

    assert len(listings) == 3
    first = listings[0]
    assert first.case_id == "11111111-1111-4111-8111-111111111111"
    assert first.address == "Eksempelvej 25"
    assert first.zip_code == 4700
    assert first.city == "Næstved"
    assert first.price == 2698000
    assert first.energy_label == "D"
    assert first.days_listed == 72
    assert first.url.startswith("https://")
    assert "/600x" in first.image

    params = aioclient_mock.mock_calls[0][1].query
    assert params["cities"] == "Næstved"
    assert params["addressTypes"] == "villa"
    assert params["priceMin"] == "1000000"
    assert "priceMax" not in params


async def test_search_pages_through_results(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, search_response
) -> None:
    """All pages are fetched until totalHits is reached."""
    case = search_response["cases"][0]
    page1 = [{**case, "caseID": f"a{i}"} for i in range(PAGE_SIZE)]
    page2 = [{**case, "caseID": f"b{i}"} for i in range(5)]
    total = PAGE_SIZE + 5
    aioclient_mock.get(
        API_URL, params={"page": "1"}, json={"cases": page1, "totalHits": total}
    )
    aioclient_mock.get(
        API_URL, params={"page": "2"}, json={"cases": page2, "totalHits": total}
    )
    client = BoligsidenClient(async_get_clientsession(hass))

    listings = await client.async_search("Aarhus C", ["villa"])

    assert len(listings) == total
    assert aioclient_mock.call_count == 2


async def test_search_empty(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A search without matches returns cases: null."""
    aioclient_mock.get(API_URL, json=EMPTY)
    client = BoligsidenClient(async_get_clientsession(hass))

    assert await client.async_search("Næstved", ["condo"]) == []


async def test_find_city(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, search_response
) -> None:
    """The canonical city name comes from the API."""
    aioclient_mock.get(API_URL, json=search_response)
    client = BoligsidenClient(async_get_clientsession(hass))

    city = await client.async_find_city("  NAESTVED ")

    assert city == "Næstved"
    assert aioclient_mock.mock_calls[0][1].query["cities"] == "NAESTVED"


async def test_find_city_unknown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An unknown city returns None."""
    aioclient_mock.get(API_URL, json=EMPTY)
    client = BoligsidenClient(async_get_clientsession(hass))

    assert await client.async_find_city("xyzzyby") is None


async def test_http_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """HTTP errors raise a connection error."""
    aioclient_mock.get(API_URL, status=403, text="Just a moment...")
    client = BoligsidenClient(async_get_clientsession(hass))

    with pytest.raises(BoligsidenConnectionError):
        await client.async_search("Næstved")


async def test_unexpected_shape(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A response without totalHits raises a response error."""
    aioclient_mock.get(API_URL, json={"something": "else"})
    client = BoligsidenClient(async_get_clientsession(hass))

    with pytest.raises(BoligsidenResponseError):
        await client.async_search("Næstved")
