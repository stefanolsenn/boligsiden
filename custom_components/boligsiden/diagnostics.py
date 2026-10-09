"""Diagnostics for the Boligsiden integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import BoligsidenConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BoligsidenConfigEntry
) -> dict[str, Any]:
    """Return search settings, listings and a raw API case for debugging."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "update_interval": str(coordinator.update_interval),
        "last_update_success": coordinator.last_update_success,
        "listing_count": len(coordinator.data or {}),
        "listings": [
            listing.as_dict() for listing in (coordinator.data or {}).values()
        ],
        "last_raw_case": coordinator.client.last_raw_case,
    }
