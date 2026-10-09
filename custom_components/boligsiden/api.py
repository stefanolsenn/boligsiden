"""Async client for the (unofficial) Boligsiden search API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import aiohttp

API_URL = "https://api.boligsiden.dk/search/cases"
PAGE_SIZE = 100
MAX_PAGES = 20
TIMEOUT = aiohttp.ClientTimeout(total=30)
USER_AGENT = "ha-boligsiden (+https://github.com/stefanolsenn/boligsiden)"

IMAGE_WIDTH = 600


class BoligsidenError(Exception):
    """Base error for the Boligsiden client."""


class BoligsidenConnectionError(BoligsidenError):
    """The API could not be reached or returned an error."""


class BoligsidenResponseError(BoligsidenError):
    """The API returned data in an unexpected shape."""


@dataclass(frozen=True, slots=True)
class Listing:
    """A single property listed for sale."""

    case_id: str
    address: str
    zip_code: int | None
    city: str | None
    property_type: str | None
    price: int | None
    price_change_percentage: float | None
    price_per_m2: int | None
    living_area: int | None
    lot_area: int | None
    rooms: int | None
    year_built: int | None
    energy_label: str | None
    days_listed: int | None
    monthly_expense: int | None
    realtor: str | None
    url: str | None
    image: str | None
    latitude: float | None
    longitude: float | None

    @classmethod
    def from_api(cls, case: dict[str, Any]) -> Listing:
        """Build a listing from a raw API case."""
        address = case.get("address") or {}
        coordinates = case.get("coordinates") or {}
        energy_label = case.get("energyLabel")
        return cls(
            case_id=case["caseID"],
            address=_format_address(address),
            zip_code=address.get("zipCode"),
            city=(address.get("city") or {}).get("name") or address.get("cityName"),
            property_type=case.get("addressType"),
            price=case.get("priceCash"),
            price_change_percentage=case.get("priceChangePercentage"),
            price_per_m2=case.get("perAreaPrice"),
            living_area=case.get("housingArea"),
            lot_area=case.get("lotArea"),
            rooms=case.get("numberOfRooms"),
            year_built=case.get("yearBuilt"),
            energy_label=energy_label.upper() if energy_label else None,
            days_listed=(case.get("daysListed") or {}).get("days"),
            monthly_expense=case.get("monthlyExpense"),
            realtor=(case.get("realtor") or {}).get("name"),
            url=case.get("caseUrl"),
            image=_pick_image(case.get("defaultImage")),
            latitude=coordinates.get("lat"),
            longitude=coordinates.get("lon"),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the listing as a plain dict."""
        return asdict(self)


def _format_address(address: dict[str, Any]) -> str:
    """Join the street, house number and optional floor and door."""
    street = " ".join(
        part for part in (address.get("roadName"), address.get("houseNumber")) if part
    )
    unit = " ".join(
        part for part in (address.get("floor"), address.get("door")) if part
    )
    if unit:
        return f"{street}, {unit}"
    return street


def _pick_image(default_image: dict[str, Any] | None) -> str | None:
    """Return the image URL closest to IMAGE_WIDTH."""
    sources = (default_image or {}).get("imageSources") or []
    sized = [s for s in sources if s.get("url") and (s.get("size") or {}).get("width")]
    if not sized:
        return None
    best = min(sized, key=lambda s: abs(s["size"]["width"] - IMAGE_WIDTH))
    return best["url"]


class BoligsidenClient:
    """Client for the Boligsiden search API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._session = session
        self.last_raw_case: dict[str, Any] | None = None

    async def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        """Do a single search request."""
        try:
            async with self._session.get(
                API_URL,
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=TIMEOUT,
            ) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError) as err:
            raise BoligsidenConnectionError(
                f"Error talking to Boligsiden: {err}"
            ) from err
        except ValueError as err:
            raise BoligsidenResponseError("Boligsiden returned invalid JSON") from err

        if not isinstance(data, dict) or "totalHits" not in data:
            raise BoligsidenResponseError("Unexpected response from Boligsiden")
        return data

    async def async_find_city(self, city: str) -> str | None:
        """Return the canonical city name, or None if no listings are found.

        The API returns the same empty result for an unknown city and for a
        search with no matches, so this searches without any other filters.
        """
        data = await self._request({"cities": city.strip(), "per_page": 1})
        cases = data.get("cases") or []
        if not cases:
            return None
        city_data = (cases[0].get("address") or {}).get("city") or {}
        return city_data.get("name") or city.strip()

    async def async_search(
        self,
        city: str,
        property_types: list[str] | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
    ) -> list[Listing]:
        """Return all listings matching the search."""
        params: dict[str, Any] = {"cities": city, "per_page": PAGE_SIZE}
        if property_types:
            params["addressTypes"] = ",".join(property_types)
        if price_min:
            params["priceMin"] = int(price_min)
        if price_max:
            params["priceMax"] = int(price_max)

        listings: list[Listing] = []
        for page in range(1, MAX_PAGES + 1):
            data = await self._request({**params, "page": page})
            cases = data.get("cases") or []
            if cases and self.last_raw_case is None:
                self.last_raw_case = cases[0]
            try:
                listings.extend(Listing.from_api(case) for case in cases)
            except (KeyError, TypeError, AttributeError) as err:
                raise BoligsidenResponseError(
                    f"Unexpected listing data from Boligsiden: {err}"
                ) from err
            if len(cases) < PAGE_SIZE or len(listings) >= data["totalHits"]:
                break
        return listings
