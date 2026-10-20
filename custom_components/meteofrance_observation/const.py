"""Constants for the Météo-France Observation integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "meteofrance_observation"

ATTRIBUTION: Final = "Données Météo-France"

PORTAL_URL: Final = "https://portail-api.meteofrance.fr"
API_PAGE_URL: Final = "https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesObservation"
TOKEN_URL: Final = "https://portail-api.meteofrance.fr/token"
API_BASE_URL: Final = "https://public-api.meteofrance.fr/public/DPObs/v1"

CONF_STATION_ID: Final = "station_id"
CONF_STATION_NAME: Final = "station_name"
CONF_ALTITUDE: Final = "altitude"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Stations publish a new observation every 6 minutes.
MIN_SCAN_INTERVAL_MINUTES: Final = 6
MAX_SCAN_INTERVAL_MINUTES: Final = 60
DEFAULT_SCAN_INTERVAL_MINUTES: Final = 10

# Number of stations proposed when searching around a location.
NEAREST_STATIONS_COUNT: Final = 20

KELVIN_OFFSET: Final = 273.15
