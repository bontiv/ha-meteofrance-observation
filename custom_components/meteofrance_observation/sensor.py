"""Sensors of the Météo-France Observation integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    DEGREE,
    PERCENTAGE,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_ALTITUDE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    KELVIN_OFFSET,
)
from .coordinator import MeteoFranceObsConfigEntry, MeteoFranceObsCoordinator

PARALLEL_UPDATES = 0


def _number(key: str) -> Callable[[dict[str, Any]], float | None]:
    def value(data: dict[str, Any]) -> float | None:
        raw = data.get(key)
        if raw is None or isinstance(raw, bool):
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    return value


def _kelvin_to_celsius(key: str) -> Callable[[dict[str, Any]], float | None]:
    raw = _number(key)

    def value(data: dict[str, Any]) -> float | None:
        kelvin = raw(data)
        return None if kelvin is None else round(kelvin - KELVIN_OFFSET, 2)

    return value


def _pascal_to_hectopascal(key: str) -> Callable[[dict[str, Any]], float | None]:
    raw = _number(key)

    def value(data: dict[str, Any]) -> float | None:
        pascal = raw(data)
        return None if pascal is None else round(pascal / 100, 1)

    return value


@dataclass(frozen=True, kw_only=True)
class MeteoFranceObsSensorDescription(SensorEntityDescription):
    """Describe a sensor built from a field of the 6-minute observation."""

    value_fn: Callable[[dict[str, Any]], float | None]


SENSORS: tuple[MeteoFranceObsSensorDescription, ...] = (
    MeteoFranceObsSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_kelvin_to_celsius("t"),
    ),
    MeteoFranceObsSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=_number("u"),
    ),
    MeteoFranceObsSensorDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_kelvin_to_celsius("td"),
    ),
    MeteoFranceObsSensorDescription(
        key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_pascal_to_hectopascal("pres"),
    ),
    MeteoFranceObsSensorDescription(
        key="sea_level_pressure",
        translation_key="sea_level_pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_pascal_to_hectopascal("pmer"),
    ),
    MeteoFranceObsSensorDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_number("ff"),
    ),
    MeteoFranceObsSensorDescription(
        key="wind_direction",
        translation_key="wind_direction",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=_number("dd"),
    ),
    MeteoFranceObsSensorDescription(
        key="wind_gust",
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_number("fxi10"),
    ),
    MeteoFranceObsSensorDescription(
        key="precipitation",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_number("rr_per"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoFranceObsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of a station."""
    coordinator = entry.runtime_data
    async_add_entities(MeteoFranceObsSensor(coordinator, description) for description in SENSORS)


class MeteoFranceObsSensor(CoordinatorEntity[MeteoFranceObsCoordinator], SensorEntity):
    """A measurement of a Météo-France observation station."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: MeteoFranceObsSensorDescription

    def __init__(
        self,
        coordinator: MeteoFranceObsCoordinator,
        description: MeteoFranceObsSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        data = coordinator.config_entry.data
        station_id = data[CONF_STATION_ID]
        self._attr_unique_id = f"{station_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, station_id)},
            name=data.get(CONF_STATION_NAME, station_id),
            manufacturer="Météo-France",
            model=f"Station {station_id}",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://meteo.data.gouv.fr",
        )
        self._station_attributes = {
            ATTR_LATITUDE: data.get(ATTR_LATITUDE),
            ATTR_LONGITUDE: data.get(ATTR_LONGITUDE),
            CONF_ALTITUDE: data.get(CONF_ALTITUDE),
        }

    @property
    def available(self) -> bool:
        """Return False when the station did not measure this value."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> float | None:
        """Return the measured value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the observation time and the station location."""
        data = self.coordinator.data or {}
        return {
            "observation_time": data.get("validity_time"),
            **self._station_attributes,
        }
