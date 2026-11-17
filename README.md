# Boligsiden for Home Assistant

Track homes for sale on [Boligsiden](https://www.boligsiden.dk) in Home Assistant. Get sensors for a saved search and events when a listing is added, changes price or is removed.

> **Unofficial.** This integration is not affiliated with or endorsed by Boligsiden. It uses the same public API as the Boligsiden website. That API is undocumented and can change without notice.

## Installation

### HACS

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stefanolsenn&repository=boligsiden&category=integration)

Or add it by hand:

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/stefanolsenn/boligsiden` with type **Integration**.
3. Install **Boligsiden** and restart Home Assistant.

## Setup

[![Open your Home Assistant instance and start setting up Boligsiden.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=boligsiden)

Go to **Settings** > **Devices & services** > **Add integration** and search for **Boligsiden**. Each entry is one saved search:

| Field | Description |
|---|---|
| City | The postal town as Boligsiden names it, e.g. `Næstved` or `Aarhus C`. |
| Property types | One or more of villa, terraced house, condo, villa apartment, cooperative, holiday house, farm, hobby farm and plots. |
| Minimum price | Optional, in DKK. |
| Maximum price | Optional, in DKK. |
| Update interval | How often to check for changes, in minutes. 5 to 1440, default 60. |

Add the integration again to track more searches. To change the price range or update interval later, open the entry and choose **Configure**.

## Sensors

Each search gets a device with four sensors:

| Sensor | State | Attributes |
|---|---|---|
| Listings | Number of homes for sale in the search | `listings`: all listings, newest first |
| Newest listing | Address of the most recently listed home | That listing's details |
| Lowest price | Price of the cheapest home, in DKK | That listing's details |
| Average price per m² | Average asking price per m², in DKK/m² | |

## Examples

The [`examples/`](examples/) folder has ready-to-use YAML:

- [`automations.yaml`](examples/automations.yaml): push notifications for new listings, price drops and removed listings.
- [`dashboard.yaml`](examples/dashboard.yaml): a dashboard for one search.

## Events

The **Listing update** event entity (e.g. `event.boligsiden_example_town_listing_update`) receives an event every time a listing changes:

| Event type | When |
|---|---|
| `new_listing` | A listing appears in the search |
| `price_changed` | A listing's price changes. Also has `old_price` and `price_difference` |
| `listing_removed` | A listing disappears from the search (sold, withdrawn or outside the price range) |

Each event carries the listing as attributes: `search`, `case_id`, `address`, `zip_code`, `city`, `property_type`, `price`, `price_change_percentage`, `price_per_m2`, `living_area`, `lot_area`, `rooms`, `year_built`, `energy_label`, `days_listed`, `monthly_expense`, `realtor`, `url`, `image`, `latitude`, `longitude`. In automations, read them as `trigger.to_state.attributes.<name>`.

