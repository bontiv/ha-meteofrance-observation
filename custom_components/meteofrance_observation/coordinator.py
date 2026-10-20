"""Data update coordinator for the Météo-France Observation integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    MeteoFranceAuthError,
    MeteoFranceError,
    MeteoFranceNotSubscribedError,
    MeteoFranceObsClient,
)
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

type MeteoFranceObsConfigEntry = ConfigEntry[MeteoFranceObsCoordinator]


class MeteoFranceObsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the latest 6-minute observation of one station."""

    config_entry: MeteoFranceObsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MeteoFranceObsConfigEntry,
        client: MeteoFranceObsClient,
    ) -> None:
        """Initialize the coordinator."""
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.data[CONF_STATION_ID]}",
            update_interval=timedelta(minutes=minutes),
        )
        self.client = client
        self.station_id: str = entry.data[CONF_STATION_ID]

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest observation."""
        try:
            return await self.client.async_get_observation(self.station_id)
        except MeteoFranceAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except MeteoFranceNotSubscribedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="not_subscribed"
            ) from err
        except MeteoFranceError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
