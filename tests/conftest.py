"""Fixtures for Boligsiden tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.boligsiden.const import (
    CONF_CITY,
    CONF_PROPERTY_TYPES,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


@pytest.fixture
def search_response() -> dict[str, Any]:
    """Return a recorded search response with three Næstved villas."""
    return json.loads((FIXTURES / "search_naestved_villa.json").read_text())


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry for Næstved villas."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Næstved",
        unique_id="naestved_villa",
        data={CONF_CITY: "Næstved", CONF_PROPERTY_TYPES: ["villa"]},
        options={CONF_SCAN_INTERVAL: 180},
    )
