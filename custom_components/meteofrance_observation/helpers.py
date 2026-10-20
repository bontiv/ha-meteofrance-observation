"""Helpers shared by the config flow and the integration setup."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MeteoFranceObsClient, TokenManager
from .const import DOMAIN


def async_get_client(
    hass: HomeAssistant, client_id: str, client_secret: str
) -> MeteoFranceObsClient:
    """Return an API client, sharing one token manager per application credential."""
    session = async_get_clientsession(hass)
    managers: dict[tuple[str, str], TokenManager] = hass.data.setdefault(DOMAIN, {})
    key = (client_id, client_secret)
    if key not in managers:
        managers[key] = TokenManager(session, client_id, client_secret)
    return MeteoFranceObsClient(session, managers[key])
