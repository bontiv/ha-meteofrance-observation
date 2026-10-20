"""Config flow for the Météo-France Observation integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_LOCATION
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

try:  # Home Assistant 2026.x replaced voluptuous with the compatible probatio.
    import probatio as vol
except ImportError:  # pragma: no cover
    import voluptuous as vol

from .api import (
    MeteoFranceAuthError,
    MeteoFranceConnectionError,
    MeteoFranceError,
    MeteoFranceNoDataError,
    MeteoFranceNotSubscribedError,
    MeteoFranceObsClient,
    decode_basic_credential,
)
from .const import (
    API_PAGE_URL,
    CONF_ALTITUDE,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
    NEAREST_STATIONS_COUNT,
    PORTAL_URL,
)
from .helpers import async_get_client
from .stations import Station, by_department, departments, nearest, station_label

_LOGGER = logging.getLogger(__name__)

CONF_AUTH_IMPLEMENTATION = "auth_implementation"
CONF_IMPLEMENTATION = "implementation"
CONF_DEPARTMENT = "department"
CONF_AUTHORIZATION = "authorization"

_PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _description_placeholders() -> dict[str, str]:
    return {"portal_url": PORTAL_URL, "api_url": API_PAGE_URL}


class MeteoFranceObsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a Météo-France observation station."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._implementations: dict[str, config_entry_oauth2_flow.AbstractOAuth2Implementation] = {}
        self._implementation: config_entry_oauth2_flow.LocalOAuth2Implementation | None = None
        self._client: MeteoFranceObsClient | None = None
        self._stations: list[Station] = []
        self._choices: list[tuple[Station, float | None]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MeteoFranceObsOptionsFlow:
        """Return the options flow."""
        return MeteoFranceObsOptionsFlow()

    async def _async_load_implementations(self) -> None:
        """Load the application credentials of the integration."""
        self._implementations = await config_entry_oauth2_flow.async_get_implementations(
            self.hass, DOMAIN
        )

    def _implementation_schema(self, default: str | None = None) -> vol.Schema:
        options = [
            SelectOptionDict(value=key, label=implementation.name)
            for key, implementation in self._implementations.items()
        ]
        return vol.Schema(
            {
                vol.Required(
                    CONF_IMPLEMENTATION, default=default or options[0]["value"]
                ): SelectSelector(SelectSelectorConfig(options=options))
            }
        )

    async def _async_store_credential(
        self, client_id: str, client_secret: str
    ) -> tuple[config_entry_oauth2_flow.LocalOAuth2Implementation | None, str | None]:
        """Save the credential in application credentials.

        Returns the implementation, or an error key when the application is
        already stored with another secret: application credentials cannot be
        updated, only deleted and added again.
        """
        await self._async_load_implementations()
        for implementation in self._implementations.values():
            if getattr(implementation, "client_id", None) == client_id:
                if getattr(implementation, "client_secret", None) == client_secret:
                    return implementation, None  # type: ignore[return-value]
                return None, "credentials_changed"

        auth_domain = slugify(f"{DOMAIN}.{client_id}")
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(client_id, client_secret, name=f"Météo-France {client_id[:8]}"),
            auth_domain,
        )
        await self._async_load_implementations()
        return self._implementations[auth_domain], None  # type: ignore[return-value]

    async def _async_check_credential(
        self, authorization: str, errors: dict[str, str]
    ) -> config_entry_oauth2_flow.LocalOAuth2Implementation | None:
        """Decode the Basic credential, check it with Météo-France and store it.

        Returns None and fills `errors` when the form must be shown again.
        """
        try:
            client_id, client_secret = decode_basic_credential(authorization)
        except ValueError:
            errors[CONF_AUTHORIZATION] = "invalid_format"
            return None

        client = async_get_client(self.hass, client_id, client_secret)
        try:
            self._stations = await client.async_get_stations()
        except MeteoFranceAuthError:
            errors["base"] = "invalid_auth"
        except MeteoFranceNotSubscribedError:
            errors["base"] = "not_subscribed"
        except MeteoFranceError:
            _LOGGER.exception("Cannot load the Météo-France station list")
            errors["base"] = "cannot_connect"
        if errors:
            return None

        implementation, error = await self._async_store_credential(client_id, client_secret)
        if error is not None:
            errors["base"] = error
            return None
        self._client = client
        return implementation

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Use stored credentials or add new ones."""
        await self._async_load_implementations()
        if not self._implementations:
            return await self.async_step_credentials()
        return self.async_show_menu(step_id="user", menu_options=["existing", "credentials"])

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the Basic credential shown by the Météo-France portal."""
        errors: dict[str, str] = {}
        if user_input is not None:
            implementation = await self._async_check_credential(
                user_input[CONF_AUTHORIZATION], errors
            )
            if implementation is not None:
                self._implementation = implementation
                return await self._async_after_stations_loaded()

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema({vol.Required(CONF_AUTHORIZATION): _PASSWORD_SELECTOR}),
            errors=errors,
            description_placeholders=_description_placeholders(),
        )

    async def async_step_existing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick stored application credentials."""
        if user_input is None and len(self._implementations) > 1:
            return self.async_show_form(
                step_id="existing", data_schema=self._implementation_schema()
            )

        key = (user_input or {}).get(CONF_IMPLEMENTATION) or next(iter(self._implementations))
        self._implementation = self._implementations[key]  # type: ignore[assignment]
        self._client = async_get_client(
            self.hass, self._implementation.client_id, self._implementation.client_secret
        )
        try:
            self._stations = await self._client.async_get_stations()
        except MeteoFranceAuthError:
            return self.async_abort(
                reason="invalid_auth", description_placeholders=_description_placeholders()
            )
        except MeteoFranceNotSubscribedError:
            return self.async_abort(
                reason="not_subscribed", description_placeholders=_description_placeholders()
            )
        except MeteoFranceError:
            _LOGGER.exception("Cannot load the Météo-France station list")
            return self.async_abort(reason="cannot_connect")
        return await self._async_after_stations_loaded()

    async def _async_after_stations_loaded(self) -> ConfigFlowResult:
        if not self._stations:
            return self.async_abort(reason="no_stations")
        return await self.async_step_search()

    async def async_step_search(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose how to search the station."""
        return self.async_show_menu(
            step_id="search", menu_options=["location", "department", "manual"]
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search the stations closest to a point of the map."""
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            self._choices = list(
                nearest(
                    self._stations,
                    location[ATTR_LATITUDE],
                    location[ATTR_LONGITUDE],
                    NEAREST_STATIONS_COUNT,
                )
            )
            return await self.async_step_station()

        home = {
            ATTR_LATITUDE: self.hass.config.latitude,
            ATTR_LONGITUDE: self.hass.config.longitude,
        }
        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema({vol.Required(CONF_LOCATION, default=home): LocationSelector()}),
        )

    async def async_step_department(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search the stations of a department."""
        if user_input is not None:
            self._choices = [
                (station, None)
                for station in by_department(self._stations, user_input[CONF_DEPARTMENT])
            ]
            return await self.async_step_station()

        options = [
            SelectOptionDict(value=code, label=f"{code} ({count})")
            for code, count in departments(self._stations).items()
        ]
        return self.async_show_form(
            step_id="department",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEPARTMENT): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                    )
                }
            ),
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Enter a known station id."""
        errors: dict[str, str] = {}
        if user_input is not None:
            station_id = user_input[CONF_STATION_ID].strip().zfill(8)
            station = next((s for s in self._stations if s.id == station_id), None)
            if station is None:
                errors[CONF_STATION_ID] = "unknown_station"
            else:
                result = await self._async_create_station_entry(station, errors)
                if result is not None:
                    return result

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_STATION_ID): TextSelector()}),
            errors=errors,
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a station among the search results."""
        errors: dict[str, str] = {}
        if user_input is not None:
            station = next(
                (s for s, _ in self._choices if s.id == user_input[CONF_STATION_ID]), None
            )
            if station is not None:
                result = await self._async_create_station_entry(station, errors)
                if result is not None:
                    return result

        options = [
            SelectOptionDict(value=station.id, label=station_label(station, distance))
            for station, distance in self._choices
        ]
        return self.async_show_form(
            step_id="station",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION_ID): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                    )
                }
            ),
            errors=errors,
        )

    async def _async_create_station_entry(
        self, station: Station, errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        """Create the entry if the station publishes 6-minute observations.

        Returns None and fills `errors` when the form must be shown again.
        """
        await self.async_set_unique_id(station.id)
        self._abort_if_unique_id_configured()

        assert self._client is not None and self._implementation is not None
        try:
            await self._client.async_get_observation(station.id)
        except MeteoFranceNoDataError:
            errors["base"] = "no_data"
            return None
        except MeteoFranceConnectionError:
            errors["base"] = "cannot_connect"
            return None
        except MeteoFranceError:
            return self.async_abort(
                reason="invalid_auth", description_placeholders=_description_placeholders()
            )

        return self.async_create_entry(
            title=station.name,
            data={
                CONF_AUTH_IMPLEMENTATION: self._implementation.domain,
                CONF_STATION_ID: station.id,
                CONF_STATION_NAME: station.name,
                ATTR_LATITUDE: station.latitude,
                ATTR_LONGITUDE: station.longitude,
                CONF_ALTITUDE: station.altitude,
            },
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle rejected credentials or a missing API subscription."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Check the access again, with new credentials or once the subscription is fixed."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            implementation: config_entry_oauth2_flow.LocalOAuth2Implementation | None
            if authorization := user_input.get(CONF_AUTHORIZATION, "").strip():
                implementation = await self._async_check_credential(authorization, errors)
            else:
                await self._async_load_implementations()
                implementation = self._implementations.get(  # type: ignore[assignment]
                    entry.data[CONF_AUTH_IMPLEMENTATION]
                )
                if implementation is None:
                    errors[CONF_AUTHORIZATION] = "credentials_required"

            if implementation is not None:
                client = async_get_client(
                    self.hass, implementation.client_id, implementation.client_secret
                )
                try:
                    await client.async_get_observation(entry.data[CONF_STATION_ID])
                except MeteoFranceAuthError:
                    errors["base"] = "invalid_auth"
                except MeteoFranceNotSubscribedError:
                    errors["base"] = "not_subscribed"
                except MeteoFranceNoDataError:
                    errors["base"] = "no_data"
                except MeteoFranceError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_AUTH_IMPLEMENTATION: implementation.domain}
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_AUTHORIZATION): _PASSWORD_SELECTOR}),
            errors=errors,
            description_placeholders={
                **_description_placeholders(),
                "station": entry.title,
            },
        )


class MeteoFranceObsOptionsFlow(OptionsFlow):
    """Change the update interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )

        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL_MINUTES,
                            max=MAX_SCAN_INTERVAL_MINUTES,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="min",
                        )
                    )
                }
            ),
        )
