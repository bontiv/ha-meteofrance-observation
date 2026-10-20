"""The Météo-France Observation integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN
from .coordinator import MeteoFranceObsConfigEntry, MeteoFranceObsCoordinator
from .helpers import async_get_client

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MeteoFranceObsConfigEntry) -> bool:
    """Set up a Météo-France observation station from a config entry."""
    try:
        implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    except ValueError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="missing_credentials"
        ) from err

    coordinator = MeteoFranceObsCoordinator(hass, entry, async_get_client(hass, implementation))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeteoFranceObsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: MeteoFranceObsConfigEntry) -> None:
    """Reload the entry when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
