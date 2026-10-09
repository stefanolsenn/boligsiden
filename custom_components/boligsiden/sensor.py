"""Sensors for a Boligsiden search."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from statistics import mean
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Listing
from .coordinator import BoligsidenCoordinator
from .entity import search_device_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import BoligsidenConfigEntry

# Fields kept per listing in the listings attribute. The full listing is in events.
ATTRIBUTE_FIELDS = (
    "case_id",
    "address",
    "property_type",
    "price",
    "price_change_percentage",
    "price_per_m2",
    "living_area",
    "lot_area",
    "rooms",
    "year_built",
    "energy_label",
    "days_listed",
    "realtor",
    "url",
    "image",
)


def _newest(listings: list[Listing]) -> Listing | None:
    """Return the listing with the fewest days on the market."""
    dated = [l for l in listings if l.days_listed is not None]
    return min(dated, key=lambda l: l.days_listed) if dated else None


def _cheapest(listings: list[Listing]) -> Listing | None:
    """Return the listing with the lowest price."""
    priced = [l for l in listings if l.price]
    return min(priced, key=lambda l: l.price) if priced else None


def _listing_attributes(listing: Listing | None) -> dict[str, Any]:
    """Return a listing's fields as attributes."""
    if listing is None:
        return {}
    return {key: getattr(listing, key) for key in ATTRIBUTE_FIELDS}


def _listings_attributes(listings: list[Listing]) -> dict[str, Any]:
    """Return all listings, newest first."""
    ordered = sorted(
        listings,
        key=lambda l: l.days_listed if l.days_listed is not None else float("inf"),
    )
    return {"listings": [_listing_attributes(l) for l in ordered]}


def _average_price_per_m2(listings: list[Listing]) -> int | None:
    """Return the average asking price per m²."""
    values = [l.price_per_m2 for l in listings if l.price_per_m2]
    return round(mean(values)) if values else None


@dataclass(frozen=True, kw_only=True)
class BoligsidenSensorEntityDescription(SensorEntityDescription):
    """Describes a Boligsiden sensor."""

    value_fn: Callable[[list[Listing]], Any]
    attributes_fn: Callable[[list[Listing]], dict[str, Any]] = lambda _: {}


SENSORS: tuple[BoligsidenSensorEntityDescription, ...] = (
    BoligsidenSensorEntityDescription(
        key="listings",
        translation_key="listings",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=len,
        attributes_fn=_listings_attributes,
    ),
    BoligsidenSensorEntityDescription(
        key="newest_listing",
        translation_key="newest_listing",
        value_fn=lambda listings: (l := _newest(listings)) and l.address,
        attributes_fn=lambda listings: _listing_attributes(_newest(listings)),
    ),
    BoligsidenSensorEntityDescription(
        key="lowest_price",
        translation_key="lowest_price",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="DKK",
        suggested_display_precision=0,
        value_fn=lambda listings: (l := _cheapest(listings)) and l.price,
        attributes_fn=lambda listings: _listing_attributes(_cheapest(listings)),
    ),
    BoligsidenSensorEntityDescription(
        key="average_price_per_m2",
        translation_key="average_price_per_m2",
        native_unit_of_measurement="DKK/m²",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_average_price_per_m2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoligsidenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for a search."""
    coordinator = entry.runtime_data
    async_add_entities(
        BoligsidenSensor(coordinator, description) for description in SENSORS
    )


class BoligsidenSensor(CoordinatorEntity[BoligsidenCoordinator], SensorEntity):
    """A sensor summarizing the listings of one search."""

    _attr_has_entity_name = True
    # The listing attributes change often and are large, so keep them out of history.
    _unrecorded_attributes = frozenset({"listings", "image", "url", "case_id"})
    entity_description: BoligsidenSensorEntityDescription

    def __init__(
        self,
        coordinator: BoligsidenCoordinator,
        description: BoligsidenSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = search_device_info(entry)

    @property
    def _listings(self) -> list[Listing]:
        return list(self.coordinator.data.values())

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self._listings)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the sensor attributes."""
        return self.entity_description.attributes_fn(self._listings)
