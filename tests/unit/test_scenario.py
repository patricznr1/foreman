# ============================================================
#  FOREMAN — tests/unit/test_scenario.py
#  Zweck: Pflicht-Test-Block für das Szenario-Modell (F3).
#  Prüft: alle mitgelieferten Szenarien parsen/validieren; ungültige Szenarien
#  werden abgelehnt (referenzielle Integrität, Enums, Drift-Konsistenz, Zeit).
#  Architektur-Einordnung: Quality Gate §10.3.
# ============================================================
from __future__ import annotations

import copy
from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from foreman.adapters.simulation.scenario import (
    Scenario,
    load_scenario_by_name,
    parse_duration,
)

BUNDLED = [
    "bearing_drift",
    "tool_wear",
    "lubrication_correlation",
    "healthy_baseline",
    "minimal_bearing_drift",
    "minimal_steady",
]


# --------------------------------------------------------------------------- #
#  Dauer-Parser
# --------------------------------------------------------------------------- #
def test_parse_duration_kombiniert() -> None:
    assert parse_duration("7d") == timedelta(days=7)
    assert parse_duration("16d14h") == timedelta(days=16, hours=14)
    assert parse_duration("2d09h") == timedelta(days=2, hours=9)
    assert parse_duration("5m") == timedelta(minutes=5)
    assert parse_duration("30s") == timedelta(seconds=30)


def test_parse_duration_ungueltig_wirft() -> None:
    for bad in ["", "7", "7x", "1w", "abc", "-3d"]:
        with pytest.raises(ValueError):
            parse_duration(bad)


# --------------------------------------------------------------------------- #
#  Mitgelieferte Szenarien validieren (Happy-Path)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", BUNDLED)
def test_alle_mitgelieferten_szenarien_validieren(name: str) -> None:
    scenario = load_scenario_by_name(name)
    assert scenario.scenario.name == name
    assert scenario.start_utc.tzinfo is not None
    assert scenario.interval_delta.total_seconds() > 0
    assert len(scenario.data_points) >= 1


def test_steady_szenarien_sind_driftfrei() -> None:
    steady = load_scenario_by_name("minimal_steady")
    assert steady.ground_truth is not None
    assert steady.ground_truth.drift_present is False
    assert all(dp.drift is None for dp in steady.data_points)


def test_drift_szenario_traegt_bekannte_wahrheit() -> None:
    drift = load_scenario_by_name("minimal_bearing_drift")
    assert drift.ground_truth is not None
    assert drift.ground_truth.drift_present is True
    drifting = [dp for dp in drift.data_points if dp.drift is not None]
    assert any(dp.drift is not None and dp.drift.type == "ramp" for dp in drifting)
    assert drift.production_runs  # Produktionsläufe vorhanden
    assert drift.maintenance_events  # Wartungsereignis vorhanden


def test_by_name_unbekannt_wirft() -> None:
    with pytest.raises(FileNotFoundError):
        load_scenario_by_name("gibt_es_nicht")


# --------------------------------------------------------------------------- #
#  Ungültige Szenarien werden abgelehnt
# --------------------------------------------------------------------------- #
def _minimal_dict() -> dict[str, Any]:
    # Aus dem validen Minimal-Szenario abgeleitet, dann gezielt kaputt gemacht.
    return copy.deepcopy(
        {
            "schema_version": 1,
            "scenario": {
                "name": "broken",
                "start": "2026-05-04T06:00:00+02:00",
                "duration": "1d",
                "sample_interval": "30m",
            },
            "line": {"label": "L"},
            "machine": {"external_id": "X-1", "label": "M"},
            "components": [{"key": "bearing", "label": "Lager", "component_type": "bearing"}],
            "seasonality": {"shifts": {"frueh": {"from": "06:00", "to": "14:00"}}},
            "data_points": [
                {
                    "key": "state",
                    "name": "machine_running",
                    "machine_level": True,
                    "kind": "digital",
                    "unit": "bool",
                    "source": "simulation",
                    "baseline": {"driven_by": "shift_schedule"},
                },
                {
                    "key": "vib",
                    "name": "vib",
                    "component": "bearing",
                    "kind": "analog",
                    "measurement_type": "signal",
                    "unit": "mm/s",
                    "source": "simulation",
                    "baseline": {"mean": 1.8, "noise_std": 0.1, "gated_by": "state"},
                },
            ],
        }
    )


def test_valides_minimal_dict_parst() -> None:
    Scenario.model_validate(_minimal_dict())  # darf nicht werfen


def test_unbekannte_komponenten_referenz_wird_abgelehnt() -> None:
    data = _minimal_dict()
    data["data_points"][1]["component"] = "gibt_es_nicht"
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_ungueltiger_kind_enum_wird_abgelehnt() -> None:
    data = _minimal_dict()
    data["data_points"][1]["kind"] = "analoge"  # Tippfehler
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_unbekanntes_feld_wird_abgelehnt() -> None:
    data = _minimal_dict()
    data["data_points"][1]["voltage_min"] = 0  # gibt es nicht
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_alarm_mit_unbekanntem_datenpunkt_wird_abgelehnt() -> None:
    data = _minimal_dict()
    data["alarms"] = [
        {"offset": "0d", "data_point": "gibt_es_nicht", "severity": "warning", "category": "hardware"}
    ]
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_variance_drift_ohne_std_multiplier_wird_abgelehnt() -> None:
    data = _minimal_dict()
    data["data_points"][1]["drift"] = {"type": "variance", "start": "1d"}
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_ramp_drift_ohne_target_delta_wird_abgelehnt() -> None:
    data = _minimal_dict()
    data["data_points"][1]["drift"] = {"type": "ramp", "start": "1d", "end": "2d"}
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_naive_startzeit_wird_abgelehnt() -> None:
    data = _minimal_dict()
    data["scenario"]["start"] = "2026-05-04T06:00:00"  # ohne tz-Offset
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_doppelte_datenpunkt_keys_werden_abgelehnt() -> None:
    data = _minimal_dict()
    data["data_points"][1]["key"] = "state"  # Duplikat
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_null_sample_interval_wird_abgelehnt() -> None:
    # '0d' ist Format-valide, ergäbe aber eine nicht fortschreitende Zeitachse.
    data = _minimal_dict()
    data["scenario"]["sample_interval"] = "0d"
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_null_duration_wird_abgelehnt() -> None:
    data = _minimal_dict()
    data["scenario"]["duration"] = "0d"
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_unbekannte_schema_version_wird_abgelehnt() -> None:
    # Unbekannte Versionen müssen früh scheitern, statt Inkompatibilität zu verschleiern.
    data = _minimal_dict()
    data["schema_version"] = 2
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)
