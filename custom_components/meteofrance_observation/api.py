"""Client for the Météo-France public observation API (DPObs)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_BASE_URL, TOKEN_URL
from .stations import Station, parse_stations

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = ClientTimeout(total=30)
# Renew the token a bit before it expires.
TOKEN_EXPIRY_MARGIN = 120


class MeteoFranceError(Exception):
    """Base error of the Météo-France API client."""


class MeteoFranceAuthError(MeteoFranceError):
    """The application credentials are rejected."""


class MeteoFranceNotSubscribedError(MeteoFranceError):
    """The application is not subscribed to the observation API."""


class MeteoFranceConnectionError(MeteoFranceError):
    """The API cannot be reached or returned an unexpected error."""


class MeteoFranceNoDataError(MeteoFranceError):
    """The station has no 6-minute observation."""


def _is_application_id(value: str) -> bool:
    """Tell if a value is a portal "Application ID": base64 of `key:secret`."""
    try:
        decoded = base64.b64decode(value.strip(), validate=True).decode("ascii")
    except ValueError:
        return False
    key, sep, secret = decoded.partition(":")
    return bool(sep and key and secret and decoded.isprintable())


def basic_credential(client_id: str, client_secret: str) -> str:
    """Return the Basic credential of the token request.

    The portal mostly shows the "Application ID" (in the curl example of
    "Générer token"), which is already the encoded credential: it is accepted
    in place of the client id.
    """
    if _is_application_id(client_id):
        return client_id.strip()
    return base64.b64encode(f"{client_id.strip()}:{client_secret.strip()}".encode()).decode()


class TokenManager:
    """Get and renew OAuth2 tokens with the client credentials grant.

    Tokens last one hour. A new token request may invalidate the previous
    token, so a single manager is shared by every config entry using the same
    application credentials.
    """

    def __init__(self, session: ClientSession, client_id: str, client_secret: str) -> None:
        """Initialize the token manager."""
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def async_get_token(self, force_refresh: bool = False) -> str:
        """Return a valid access token, requesting a new one when needed."""
        async with self._lock:
            if not force_refresh and self._token and time.monotonic() < self._expires_at:
                return self._token

            basic = basic_credential(self._client_id, self._client_secret)
            try:
                async with self._session.post(
                    TOKEN_URL,
                    params={"grant_type": "client_credentials"},
                    headers={"Authorization": f"Basic {basic}"},
                    timeout=REQUEST_TIMEOUT,
                ) as response:
                    if response.status in (400, 401, 403):
                        raise MeteoFranceAuthError(
                            f"Token request rejected with status {response.status}"
                        )
                    if response.status != 200:
                        raise MeteoFranceConnectionError(
                            f"Token request failed with status {response.status}"
                        )
                    data = await response.json(content_type=None)
            except (ClientError, TimeoutError) as err:
                raise MeteoFranceConnectionError(f"Token request failed: {err}") from err

            try:
                self._token = data["access_token"]
                expires_in = int(data.get("expires_in", 3600))
            except (KeyError, TypeError, ValueError) as err:
                raise MeteoFranceAuthError("Invalid token response") from err
            self._expires_at = time.monotonic() + max(expires_in - TOKEN_EXPIRY_MARGIN, 60)
            _LOGGER.debug("New Météo-France token, valid for %s s", expires_in)
            return self._token


class MeteoFranceObsClient:
    """Read stations and observations from the DPObs API."""

    def __init__(self, session: ClientSession, token_manager: TokenManager) -> None:
        """Initialize the client."""
        self._session = session
        self._token_manager = token_manager

    async def _async_get(self, path: str, params: dict[str, str] | None = None) -> str:
        """Run an authenticated GET request and return the response body."""
        for attempt in range(2):
            # A 401 means the token was revoked: request a new one and retry once.
            token = await self._token_manager.async_get_token(force_refresh=attempt > 0)
            try:
                async with self._session.get(
                    f"{API_BASE_URL}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=REQUEST_TIMEOUT,
                ) as response:
                    status = response.status
                    body = await response.text()
            except (ClientError, TimeoutError) as err:
                raise MeteoFranceConnectionError(f"Request to {path} failed: {err}") from err

            if status == 401 and attempt == 0:
                continue
            if status == 200:
                return body
            if status == 401:
                raise MeteoFranceAuthError(f"Request to {path} unauthorized")
            if status == 403:
                raise MeteoFranceNotSubscribedError(f"Request to {path} forbidden")
            if status in (204, 400, 404):
                raise MeteoFranceNoDataError(f"No data for {path} ({status})")
            raise MeteoFranceConnectionError(f"Request to {path} failed with status {status}")
        raise MeteoFranceAuthError(f"Request to {path} unauthorized")

    async def async_get_stations(self) -> list[Station]:
        """Return every station of the observation network."""
        return parse_stations(await self._async_get("/liste-stations"))

    async def async_get_observation(self, station_id: str) -> dict[str, Any]:
        """Return the latest 6-minute observation of a station."""
        body = await self._async_get(
            "/station/infrahoraire-6m", {"id_station": station_id, "format": "json"}
        )
        try:
            data = json.loads(body)
        except ValueError as err:
            raise MeteoFranceConnectionError("Invalid observation response") from err
        if isinstance(data, dict):
            data = [data]
        records = (
            [record for record in data if isinstance(record, dict)]
            if isinstance(data, list)
            else []
        )
        if not records:
            raise MeteoFranceNoDataError(f"No observation for station {station_id}")
        return max(records, key=lambda record: record.get("validity_time") or "")
