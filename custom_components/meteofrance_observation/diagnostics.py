"""Diagnostics for the Météo-France Observation integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import MeteoFranceObsConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MeteoFranceObsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The entry holds no secret: credentials live in application credentials
    and tokens only in memory.
    """
    coordinator = entry.runtime_data
    return {
        "entry_data": dict(entry.data),
        "options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
        "observation": coordinator.data,
    }
