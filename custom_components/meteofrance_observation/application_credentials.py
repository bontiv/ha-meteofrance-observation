"""Application credentials for the Météo-France Observation integration.

Météo-France uses the OAuth2 client credentials grant: there is no browser
redirection. The credentials are only stored here; tokens are requested by
`api.TokenManager`.
"""

from __future__ import annotations

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import API_PAGE_URL, PORTAL_URL, TOKEN_URL


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return the implementation holding the client id and secret."""
    return AuthImplementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(authorize_url=PORTAL_URL, token_url=TOKEN_URL),
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return the placeholders of the credentials dialog description."""
    return {"portal_url": PORTAL_URL, "api_url": API_PAGE_URL}
