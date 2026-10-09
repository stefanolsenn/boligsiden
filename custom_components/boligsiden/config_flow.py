"""Config flow for the Boligsiden integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import slugify

from . import BoligsidenConfigEntry
from .api import BoligsidenClient, BoligsidenError
from .const import (
    CONF_CITY,
    CONF_PRICE_MAX,
    CONF_PRICE_MIN,
    CONF_PROPERTY_TYPES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    PROPERTY_TYPES,
)

PRICE_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=0, step=25000, mode=NumberSelectorMode.BOX, unit_of_measurement="DKK"
    )
)

PROPERTY_TYPE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=list(PROPERTY_TYPES),
        multiple=True,
        mode=SelectSelectorMode.LIST,
        translation_key="property_type",
    )
)

SCAN_INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=MIN_SCAN_INTERVAL,
        max=MAX_SCAN_INTERVAL,
        step=15,
        mode=NumberSelectorMode.BOX,
        unit_of_measurement="min",
    )
)


def _price_errors(user_input: dict[str, Any]) -> dict[str, str]:
    """Check that min price is not above max price."""
    price_min = user_input.get(CONF_PRICE_MIN)
    price_max = user_input.get(CONF_PRICE_MAX)
    if price_min and price_max and price_min > price_max:
        return {CONF_PRICE_MAX: "price_range"}
    return {}


def _options_from_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Pick the options from the form input, dropping empty prices."""
    options: dict[str, Any] = {
        CONF_SCAN_INTERVAL: int(
            user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
    }
    for key in (CONF_PRICE_MIN, CONF_PRICE_MAX):
        if user_input.get(key):
            options[key] = int(user_input[key])
    return options


class BoligsidenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up one saved search per config entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for city, property types, price range and update interval."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _price_errors(user_input)
            if not user_input[CONF_PROPERTY_TYPES]:
                errors[CONF_PROPERTY_TYPES] = "no_property_types"

            if not errors:
                client = BoligsidenClient(async_get_clientsession(self.hass))
                try:
                    city = await client.async_find_city(user_input[CONF_CITY])
                except BoligsidenError:
                    LOGGER.exception("Could not reach Boligsiden")
                    errors["base"] = "cannot_connect"
                else:
                    if city is None:
                        errors[CONF_CITY] = "city_not_found"

            if not errors:
                property_types = sorted(user_input[CONF_PROPERTY_TYPES])
                await self.async_set_unique_id(
                    f"{slugify(city)}_{'_'.join(property_types)}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=city,
                    data={CONF_CITY: city, CONF_PROPERTY_TYPES: property_types},
                    options=_options_from_input(user_input),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_CITY): TextSelector(),
                        vol.Required(
                            CONF_PROPERTY_TYPES, default=["villa"]
                        ): PROPERTY_TYPE_SELECTOR,
                        vol.Optional(CONF_PRICE_MIN): PRICE_SELECTOR,
                        vol.Optional(CONF_PRICE_MAX): PRICE_SELECTOR,
                        vol.Required(
                            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                        ): SCAN_INTERVAL_SELECTOR,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: BoligsidenConfigEntry,
    ) -> BoligsidenOptionsFlow:
        """Return the options flow."""
        return BoligsidenOptionsFlow()


class BoligsidenOptionsFlow(OptionsFlowWithReload):
    """Change price range and poll interval for a search."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _price_errors(user_input)
            if not errors:
                return self.async_create_entry(data=_options_from_input(user_input))

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(CONF_PRICE_MIN): PRICE_SELECTOR,
                        vol.Optional(CONF_PRICE_MAX): PRICE_SELECTOR,
                        vol.Required(
                            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                        ): SCAN_INTERVAL_SELECTOR,
                    }
                ),
                user_input or self.config_entry.options,
            ),
            errors=errors,
        )
