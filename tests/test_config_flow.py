"""Tests of the config flow."""

from __future__ import annotations

import base64

from homeassistant import config_entries
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.config_entry_oauth2_flow import async_get_implementations
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.meteofrance_observation.const import (
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    DOMAIN,
)

from .conftest import OBSERVATION_URL, STATIONS_URL, mock_api, mock_token

NEW_BASIC = base64.b64encode(b"new-id:new-secret").decode()


async def _init(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def _start(hass: HomeAssistant):
    """Start the flow with the stored credentials, up to the search menu."""
    result = await _init(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["existing", "credentials"]
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "existing"}
    )


@pytest.mark.parametrize(
    "authorization",
    [NEW_BASIC, f"Basic {NEW_BASIC}", f"Authorization: Basic {NEW_BASIC}", f"  '{NEW_BASIC}' "],
)
async def test_new_credentials(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, authorization: str
) -> None:
    """The Basic value is decoded and saved in application credentials."""
    mock_api(aioclient_mock)
    result = await _init(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"authorization": authorization}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "search"
    token_call = next(call for call in aioclient_mock.mock_calls if call[0] == "POST")
    assert token_call[3]["Authorization"] == f"Basic {NEW_BASIC}"

    credentials = await async_get_implementations(hass, DOMAIN)
    implementation = credentials["meteofrance_observation_new_id"]
    assert (implementation.client_id, implementation.client_secret) == ("new-id", "new-secret")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "75110001"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["auth_implementation"] == "meteofrance_observation_new_id"


@pytest.mark.parametrize(
    ("token_status", "stations_status", "errors"),
    [
        (401, 200, {"base": "invalid_auth"}),
        (200, 403, {"base": "not_subscribed"}),
        (200, 500, {"base": "cannot_connect"}),
    ],
)
async def test_new_credentials_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    token_status: int,
    stations_status: int,
    errors: dict[str, str],
) -> None:
    """Rejected credentials are reported in the form and not saved."""
    mock_token(aioclient_mock, status=token_status)
    aioclient_mock.get(STATIONS_URL, status=stations_status, text="")
    result = await _init(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"authorization": NEW_BASIC}
    )
    assert result["step_id"] == "credentials"
    assert result["errors"] == errors
    assert await async_get_implementations(hass, DOMAIN) == {}


@pytest.mark.parametrize("authorization", ["not base64!", base64.b64encode(b"no-colon").decode()])
async def test_invalid_format(hass: HomeAssistant, authorization: str) -> None:
    """A value that does not decode to id:secret is refused."""
    result = await _init(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"authorization": authorization}
    )
    assert result["errors"] == {"authorization": "invalid_format"}


@pytest.mark.usefixtures("credentials")
async def test_credentials_changed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A stored application with another secret cannot be updated."""
    mock_api(aioclient_mock)
    result = await _init(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "credentials"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"authorization": base64.b64encode(b"client-id:other-secret").decode()},
    )
    assert result["errors"] == {"base": "credentials_changed"}


@pytest.mark.usefixtures("credentials")
async def test_location_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Pick the nearest station around a point."""
    mock_api(aioclient_mock)
    result = await _start(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["location", "department", "manual"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "location"}
    )
    assert result["step_id"] == "location"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATION: {ATTR_LATITUDE: 48.88, ATTR_LONGITUDE: 2.35}}
    )
    assert result["step_id"] == "station"
    options = result["data_schema"].schema[CONF_STATION_ID].config["options"]
    assert options[0] == {
        "value": "75110001",
        "label": "PARIS-LARIBOISIERE (75110001) – 0.3 km – 52 m",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "75110001"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PARIS-LARIBOISIERE"
    assert result["result"].unique_id == "75110001"
    assert result["data"] == {
        "auth_implementation": DOMAIN,
        "station_id": "75110001",
        "station_name": "PARIS-LARIBOISIERE",
        "latitude": 48.882,
        "longitude": 2.352,
        "altitude": 52,
    }
    # One token request is shared by the station list and the observation.
    token_calls = [call for call in aioclient_mock.mock_calls if call[0] == "POST"]
    assert len(token_calls) == 1


@pytest.mark.usefixtures("credentials")
async def test_department_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Pick a station of a department."""
    mock_api(aioclient_mock)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "department"}
    )
    options = result["data_schema"].schema["department"].config["options"]
    assert {"value": "75", "label": "75 (2)"} in options
    assert {"value": "972", "label": "972 (1)"} in options

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"department": "75"})
    options = result["data_schema"].schema[CONF_STATION_ID].config["options"]
    assert [option["value"] for option in options] == ["75110001", "75114001"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "75114001"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PARIS-MONTSOURIS"


@pytest.mark.usefixtures("credentials")
async def test_manual_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Enter a station id, with the leading zero restored."""
    mock_api(aioclient_mock)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "12345678"}
    )
    assert result["errors"] == {CONF_STATION_ID: "unknown_station"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: " 1014002 "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["station_id"] == "01014002"


@pytest.mark.usefixtures("credentials")
async def test_station_without_data(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A station without 6-minute observations shows an error."""
    mock_api(aioclient_mock, observation=[])
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "75110001"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_data"}


@pytest.mark.parametrize(
    ("token_status", "stations_status", "reason"),
    [
        (401, 200, "invalid_auth"),
        (200, 403, "not_subscribed"),
        (200, 500, "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("credentials")
async def test_credentials_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    token_status: int,
    stations_status: int,
    reason: str,
) -> None:
    """Stored credentials that are rejected abort the flow."""
    mock_token(aioclient_mock, status=token_status)
    aioclient_mock.get(STATIONS_URL, status=stations_status, text="")
    result = await _start(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("credentials")
async def test_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """A station can only be added once."""
    config_entry.add_to_hass(hass)
    mock_api(aioclient_mock)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "75110001"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("credentials")
async def test_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Reauthentication checks the station again."""
    config_entry.add_to_hass(hass)
    mock_token(aioclient_mock)
    aioclient_mock.get(OBSERVATION_URL, status=403, text="")
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "not_subscribed"}

    aioclient_mock.clear_requests()
    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("credentials")
async def test_reauth_new_credentials(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Reauthentication accepts new credentials."""
    config_entry.add_to_hass(hass)
    mock_api(aioclient_mock)
    result = await config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"authorization": f"Basic {NEW_BASIC}"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["auth_implementation"] == "meteofrance_observation_new_id"


async def test_options(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """The update interval can be changed."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 15}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_SCAN_INTERVAL: 15}
