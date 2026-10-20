"""Tests of the setup and the sensors."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.meteofrance_observation.const import DOMAIN

from .conftest import OBSERVATION, OBSERVATION_URL, mock_api, mock_token


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("credentials")
async def test_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Temperature and humidity are enabled and converted."""
    mock_api(aioclient_mock)
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    temperature = hass.states.get("sensor.paris_lariboisiere_temperature")
    assert temperature is not None
    assert float(temperature.state) == pytest.approx(10.6)
    assert temperature.attributes["unit_of_measurement"] == "°C"
    assert temperature.attributes["device_class"] == "temperature"
    assert temperature.attributes["observation_time"] == "2026-10-20T08:06:00Z"
    assert temperature.attributes["attribution"] == "Données Météo-France"

    humidity = hass.states.get("sensor.paris_lariboisiere_humidity")
    assert humidity is not None and float(humidity.state) == 84

    pressure = entity_registry.async_get("sensor.paris_lariboisiere_atmospheric_pressure")
    assert pressure is not None
    assert pressure.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "75110001_dew_point")


@pytest.mark.usefixtures("credentials")
async def test_missing_value_is_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """A null measurement makes the sensor unavailable."""
    mock_api(aioclient_mock, observation=[{**OBSERVATION[0], "t": None}])
    await _setup(hass, config_entry)
    assert hass.states.get("sensor.paris_lariboisiere_temperature").state == STATE_UNAVAILABLE
    assert float(hass.states.get("sensor.paris_lariboisiere_humidity").state) == 84


@pytest.mark.usefixtures("credentials")
async def test_revoked_token_is_renewed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A 401 triggers a new token request and a retry."""
    mock_api(aioclient_mock)
    await _setup(hass, config_entry)

    aioclient_mock.clear_requests()
    mock_token(aioclient_mock)
    aioclient_mock.get(OBSERVATION_URL, status=401, text="")
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Request, new token, retry: still 401, so a reauth flow starts.
    assert [call[0] for call in aioclient_mock.mock_calls] == ["GET", "POST", "GET"]
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


@pytest.mark.usefixtures("credentials")
async def test_station_down_retries(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """An API error at startup retries the setup later."""
    mock_token(aioclient_mock)
    aioclient_mock.get(OBSERVATION_URL, status=500, text="")
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_removed_credentials(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Removed application credentials prevent the setup."""
    await _setup(hass, config_entry)
    assert config_entry.state in (ConfigEntryState.SETUP_ERROR, ConfigEntryState.SETUP_RETRY)


@pytest.mark.usefixtures("credentials")
async def test_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """The entry unloads cleanly."""
    mock_api(aioclient_mock)
    await _setup(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
