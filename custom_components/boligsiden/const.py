"""Constants for the Boligsiden integration."""

from __future__ import annotations

from datetime import timedelta
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "boligsiden"

CONF_CITY = "city"
CONF_PROPERTY_TYPES = "property_types"
CONF_PRICE_MIN = "price_min"
CONF_PRICE_MAX = "price_max"
CONF_SCAN_INTERVAL = "scan_interval"

# Minutes. Kept conservative since the API is unofficial.
DEFAULT_SCAN_INTERVAL = 180
MIN_SCAN_INTERVAL = 60
MAX_SCAN_INTERVAL = 1440

# Spread requests from many installs so they don't hit the API at the same time.
MAX_JITTER = timedelta(minutes=10)

# Property type keys used in the config entry and translations, mapped to the
# values the API's addressTypes parameter accepts. Translation keys can't
# contain spaces, so the keys differ from the API values.
PROPERTY_TYPES = {
    "villa": "villa",
    "terraced_house": "terraced house",
    "condo": "condo",
    "villa_apartment": "villa apartment",
    "cooperative": "cooperative",
    "holiday_house": "holiday house",
    "farm": "farm",
    "hobby_farm": "hobby farm",
    "full_year_plot": "full year plot",
    "holiday_plot": "holiday plot",
}

EVENT_NEW_LISTING = f"{DOMAIN}_new_listing"
EVENT_PRICE_CHANGED = f"{DOMAIN}_price_changed"
EVENT_LISTING_REMOVED = f"{DOMAIN}_listing_removed"

STORAGE_VERSION = 1
