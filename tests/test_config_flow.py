"""Tests for the Boligsiden config flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.boligsiden.api import API_URL
from custom_components.boligsiden.const import (
    CONF_CITY,
    CONF_PRICE_MAX,
    CONF_PRICE_MIN,
    CONF_PROPERTY_TYPES,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

USER_INPUT = {
    CONF_CITY: "naestved",
    CONF_PROPERTY_TYPES: ["villa", "terraced_house"],
    CONF_PRICE_MAX: 3_000_000,
    CONF_SCAN_INTERVAL: 120,
}


async def _start(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return result["flow_id"]


async def test_user_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, search_response
) -> None:
    """A valid city creates an entry named by the API."""
    aioclient_mock.get(API_URL, json=search_response)
    flow_id = await _start(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Næstved"
    assert result["data"] == {
        CONF_CITY: "Næstved",
        CONF_PROPERTY_TYPES: ["terraced_house", "villa"],
    }
    assert result["options"] == {CONF_PRICE_MAX: 3_000_000, CONF_SCAN_INTERVAL: 120}
    assert result["result"].unique_id == "naestved_terraced_house_villa"


async def test_user_flow_city_not_found(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, search_response
) -> None:
    """An unknown city shows an error, and the user can fix it."""
    aioclient_mock.get(
        API_URL, params={"cities": "tjareborg"}, json={"cases": None, "totalHits": 0}
    )
    aioclient_mock.get(API_URL, json=search_response)
    flow_id = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {**USER_INPUT, CONF_CITY: "tjareborg"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_CITY: "city_not_found"}

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Connection errors show a form error."""
    aioclient_mock.get(API_URL, status=500)
    flow_id = await _start(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_bad_price_range(hass: HomeAssistant) -> None:
    """Min price above max price is rejected without calling the API."""
    flow_id = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {**USER_INPUT, CONF_PRICE_MIN: 4_000_000}
    )

    assert result["errors"] == {CONF_PRICE_MAX: "price_range"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, search_response
) -> None:
    """The same city and property types can't be added twice."""
    MockConfigEntry(
        domain=DOMAIN, unique_id="naestved_terraced_house_villa"
    ).add_to_hass(hass)
    aioclient_mock.get(API_URL, json=search_response)
    flow_id = await _start(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    search_response,
    config_entry: MockConfigEntry,
) -> None:
    """Options update the price range and interval."""
    aioclient_mock.get(API_URL, json=search_response)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_PRICE_MIN: 1_500_000, CONF_SCAN_INTERVAL: 240}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_PRICE_MIN: 1_500_000, CONF_SCAN_INTERVAL: 240}
