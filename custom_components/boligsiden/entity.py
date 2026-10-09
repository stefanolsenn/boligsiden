"""Shared entity helpers for the Boligsiden integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import CONF_PROPERTY_TYPES, DOMAIN, PROPERTY_TYPES


def search_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return the device that groups the entities of one search."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Boligsiden {entry.title}",
        model=", ".join(PROPERTY_TYPES[key] for key in entry.data[CONF_PROPERTY_TYPES]),
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://www.boligsiden.dk",
    )
