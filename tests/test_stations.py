"""Tests of the station helpers and the credential handling."""

from __future__ import annotations

import base64

import pytest

from custom_components.meteofrance_observation.api import basic_credential
from custom_components.meteofrance_observation.stations import (
    by_department,
    department_of,
    departments,
    haversine,
    nearest,
    parse_stations,
    station_label,
)

from .conftest import STATIONS_CSV


def test_parse_stations() -> None:
    """Rows without coordinates are skipped and leading zeros restored."""
    stations = parse_stations(STATIONS_CSV)
    ids = [station.id for station in stations]
    assert ids == ["75110001", "75114001", "92073001", "69029001", "01014002", "97209001"]
    assert stations[0].name == "PARIS-LARIBOISIERE"
    assert stations[0].altitude == 52
    assert stations[0].pack == "RADOME"


@pytest.mark.parametrize(
    ("station_id", "department"),
    [("75110001", "75"), ("01014002", "01"), ("97209001", "972"), ("20004002", "20")],
)
def test_department_of(station_id: str, department: str) -> None:
    """Overseas departments use 3 digits."""
    assert department_of(station_id) == department


def test_haversine() -> None:
    """Paris to Lyon is about 392 km."""
    assert haversine(48.8566, 2.3522, 45.764, 4.8357) == pytest.approx(392, abs=2)


def test_nearest_and_departments() -> None:
    """Search helpers sort by distance or by name."""
    stations = parse_stations(STATIONS_CSV)
    result = nearest(stations, 48.88, 2.35, 3)
    assert [station.id for station, _ in result] == ["75110001", "75114001", "92073001"]
    assert result[0][1] < 1
    assert departments(stations) == {"01": 1, "69": 1, "75": 2, "92": 1, "972": 1}
    assert [s.name for s in by_department(stations, "75")] == [
        "PARIS-LARIBOISIERE",
        "PARIS-MONTSOURIS",
    ]
    assert station_label(stations[0], 0.42) == "PARIS-LARIBOISIERE (75110001) – 0.4 km – 52 m"


def test_basic_credential() -> None:
    """The portal Application ID is accepted in place of the client id."""
    expected = base64.b64encode(b"key:secret").decode()
    assert basic_credential("key", "secret") == expected
    assert basic_credential(expected, "anything") == expected
    assert basic_credential(expected, expected) == expected
