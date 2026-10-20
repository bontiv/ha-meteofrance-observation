"""Fixtures for the Météo-France Observation tests."""

from __future__ import annotations

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.meteofrance_observation.const import (
    API_BASE_URL,
    CONF_ALTITUDE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    TOKEN_URL,
)

STATIONS_URL = f"{API_BASE_URL}/liste-stations"
OBSERVATION_URL = f"{API_BASE_URL}/station/infrahoraire-6m"

STATIONS_CSV = (
    "﻿Id_station;Id_omm;Nom_usuel;Latitude;Longitude;Altitude;Date_ouverture;Pack\n"
    "75110001;;PARIS-LARIBOISIERE;48.882;2.352;52;2015-01-01;RADOME\n"
    "75114001;07156;PARIS-MONTSOURIS;48.8217;2.3378;75;1872-01-01;RADOME\n"
    "92073001;;SURESNES;48.871;2.226;42;2000-01-01;ETENDU\n"
    "69029001;07480;LYON-BRON;45.7217;4.9467;198;1920-01-01;RADOME\n"
    "1014002;;ARBENT;46.278;5.669;534;1990-01-01;ETENDU\n"
    "97209001;;FORT DE FRANCE;14.6;-61.07;5;1990-01-01;RADOME\n"
    "13999999;;SANS COORDONNEES;;;;;\n"
)

OBSERVATION = [
    {
        "geo_id_insee": "75110001",
        "reference_time": "2026-10-20T08:12:00Z",
        "insert_time": "2026-10-20T08:10:00Z",
        "validity_time": "2026-10-20T08:06:00Z",
        "t": 283.75,
        "td": 281.15,
        "u": 84,
        "dd": 220,
        "ff": 3.2,
        "fxi10": 5.1,
        "rr_per": 0.2,
        "pres": 101325,
        "pmer": 101530,
    }
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable the custom integration in every test."""
    return


@pytest.fixture
async def credentials(hass: HomeAssistant) -> None:
    """Register application credentials for the integration."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential("client-id", "client-secret"), DOMAIN
    )


def mock_token(aioclient_mock: AiohttpClientMocker, status: int = 200) -> None:
    """Mock the token endpoint."""
    aioclient_mock.post(
        TOKEN_URL,
        status=status,
        json={"access_token": "token", "token_type": "Bearer", "expires_in": 3600},
    )


def mock_api(
    aioclient_mock: AiohttpClientMocker,
    observation: list | None = None,
    observation_status: int = 200,
) -> None:
    """Mock the token, station list and observation endpoints."""
    mock_token(aioclient_mock)
    aioclient_mock.get(STATIONS_URL, text=STATIONS_CSV)
    aioclient_mock.get(
        OBSERVATION_URL,
        status=observation_status,
        json=OBSERVATION if observation is None else observation,
    )


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return the config entry of the Paris-Lariboisière station."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="PARIS-LARIBOISIERE",
        unique_id="75110001",
        data={
            "auth_implementation": DOMAIN,
            CONF_STATION_ID: "75110001",
            CONF_STATION_NAME: "PARIS-LARIBOISIERE",
            ATTR_LATITUDE: 48.882,
            ATTR_LONGITUDE: 2.352,
            CONF_ALTITUDE: 52,
        },
    )
