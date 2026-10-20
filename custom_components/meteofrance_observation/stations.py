"""Station list parsing and search helpers.

The station list has about 2000 rows: a plain haversine distance over every
station is cheap enough to run in the event loop, no geo library needed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True, slots=True)
class Station:
    """A Météo-France observation station."""

    id: str
    name: str
    latitude: float
    longitude: float
    altitude: int | None = None
    pack: str | None = None

    @property
    def department(self) -> str:
        """Return the department code of the station."""
        return department_of(self.id)


def department_of(station_id: str) -> str:
    """Return the department code from an 8-digit station id.

    Station ids start with the department number: 75110001 is in Paris (75),
    01014002 is in Ain (01). Overseas departments use 3 digits (971 to 976).
    """
    if station_id.startswith(("97", "98")):
        return station_id[:3]
    return station_id[:2]


def _to_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        return float(value.strip().replace(",", "."))
    except ValueError:
        return None


def parse_stations(text: str) -> list[Station]:
    """Parse the CSV returned by the /liste-stations endpoint.

    Columns are separated by semicolons. Rows without coordinates are skipped.
    """
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter=";")
    stations: list[Station] = []
    for raw in reader:
        row = {(key or "").strip().lower(): (value or "").strip() for key, value in raw.items()}
        station_id = row.get("id_station", "")
        latitude = _to_float(row.get("latitude"))
        longitude = _to_float(row.get("longitude"))
        if not station_id or latitude is None or longitude is None:
            continue
        # Spreadsheets drop the leading zero of departments 01 to 09.
        station_id = station_id.zfill(8)
        altitude = _to_float(row.get("altitude"))
        stations.append(
            Station(
                id=station_id,
                name=row.get("nom_usuel") or station_id,
                latitude=latitude,
                longitude=longitude,
                altitude=round(altitude) if altitude is not None else None,
                pack=row.get("pack") or None,
            )
        )
    return stations


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in kilometers between two points."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def nearest(
    stations: list[Station], latitude: float, longitude: float, count: int
) -> list[tuple[Station, float]]:
    """Return the `count` stations closest to a point, with their distance in km."""
    with_distance = [
        (station, haversine(latitude, longitude, station.latitude, station.longitude))
        for station in stations
    ]
    with_distance.sort(key=lambda item: item[1])
    return with_distance[:count]


def departments(stations: list[Station]) -> dict[str, int]:
    """Return the department codes with their number of stations, sorted by code."""
    counts: dict[str, int] = {}
    for station in stations:
        counts[station.department] = counts.get(station.department, 0) + 1
    return dict(sorted(counts.items()))


def by_department(stations: list[Station], department: str) -> list[Station]:
    """Return the stations of a department, sorted by name."""
    return sorted(
        (station for station in stations if station.department == department),
        key=lambda station: station.name,
    )


def station_label(station: Station, distance: float | None = None) -> str:
    """Return a human readable label for a station selector option."""
    parts = [f"{station.name} ({station.id})"]
    if distance is not None:
        parts.append(f"{distance:.1f} km")
    if station.altitude is not None:
        parts.append(f"{station.altitude} m")
    return " – ".join(parts)
