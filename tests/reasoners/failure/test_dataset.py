# ============================================================
#  FOREMAN — tests/reasoners/failure/test_dataset.py
#  Zweck: Pflicht-Test-Block des Trainingsdatensatz-Baus (F-PRED, rein/netzfrei).
#  Prüft: Label aus ground_truth.failure + Horizont (positiv = Vorlauf vor dem
#         Ausfall), healthy = nur Negative, lauf-disjunkter Split (kein zeilen-
#         weises Mischen), dokumentierte Klassenbalance.
#  Architektur-Einordnung: Quality Gate §10.3 (reine Funktion, ohne DB).
# ============================================================
from __future__ import annotations

import copy
from datetime import timedelta
from typing import Any

import pytest

from foreman.adapters.simulation.scenario import Scenario
from foreman.reasoners.failure.dataset import (
    TrainingDataset,
    build_dataset,
    split_by_seed,
)

_HORIZON = timedelta(hours=24)


def _failure_scenario_dict() -> dict[str, Any]:
    """Kleines Szenario mit Drift + Ausfall — kurz gehalten für schnelle Tests."""
    return copy.deepcopy(
        {
            "schema_version": 1,
            "scenario": {
                "name": "tiny_failure",
                "start": "2026-03-02T00:00:00+00:00",  # Montag
                "duration": "3d",
                "sample_interval": "30m",
            },
            "line": {"label": "L"},
            "machine": {"external_id": "X-1", "label": "M", "machine_class": "cnc"},
            "components": [{"key": "bearing", "label": "Lager", "component_type": "bearing"}],
            "seasonality": {"shifts": {"tag": {"from": "06:00", "to": "22:00"}}},
            "data_points": [
                {
                    "key": "state",
                    "name": "machine_running",
                    "machine_level": True,
                    "kind": "digital",
                    "measurement_type": "signal",
                    "unit": "bool",
                    "source": "simulation",
                    "baseline": {"driven_by": "shift_schedule"},
                },
                {
                    "key": "vib",
                    "name": "vibration_rms_velocity_spindle_bearing",
                    "component": "bearing",
                    "kind": "analog",
                    "measurement_type": "signal",
                    "unit": "mm/s",
                    "source": "simulation",
                    "baseline": {"mean": 1.8, "noise_std": 0.1, "gated_by": "state"},
                    "drift": {
                        "type": "ramp",
                        "start": "1d",
                        "end": "3d",
                        "target_delta": 5.0,
                        "shape": "progressive",
                    },
                },
            ],
            "ground_truth": {
                "drift_present": True,
                "failure": {"offset": "2d12h", "type": "bearing_failure"},
            },
        }
    )


def _healthy_scenario_dict() -> dict[str, Any]:
    data = _failure_scenario_dict()
    data["scenario"]["name"] = "tiny_healthy"
    data["data_points"][1].pop("drift")
    data["ground_truth"] = {"drift_present": False}
    return data


def _failure_scenario() -> Scenario:
    return Scenario.model_validate(_failure_scenario_dict())


def _healthy_scenario() -> Scenario:
    return Scenario.model_validate(_healthy_scenario_dict())


def _by_ref_hours(dataset: TrainingDataset, hours: float) -> int:
    """Label des Samples, dessen reference_time h Stunden nach Szenario-Start liegt."""
    start = _failure_scenario().start_utc
    target = start + timedelta(hours=hours)
    matches = [s for s in dataset.samples if s.reference_time == target]
    assert len(matches) == 1, f"kein eindeutiges Sample bei {hours}h"
    return matches[0].label


# --------------------------------------------------------------------------- #
#  Label aus ground_truth.failure + Horizont
# --------------------------------------------------------------------------- #
def test_positiv_label_im_vorlauf_vor_dem_ausfall() -> None:
    # Ausfall bei 60h, Horizont 24h → ref in [36h, 60h] ist positiv.
    ds = build_dataset([(_failure_scenario(), 1)], horizon=_HORIZON, step=timedelta(hours=12))
    assert _by_ref_hours(ds, 36.0) == 1
    assert _by_ref_hours(ds, 48.0) == 1


def test_negativ_label_weit_vor_dem_ausfall() -> None:
    # ref=24h: Ausfall (60h) liegt NICHT im Horizont [24h, 48h] → negativ.
    ds = build_dataset([(_failure_scenario(), 1)], horizon=_HORIZON, step=timedelta(hours=12))
    assert _by_ref_hours(ds, 24.0) == 0


def test_keine_referenzzeit_nach_dem_ausfall() -> None:
    # Nach dem Ausfall wird nicht mehr vorhergesagt (last_ref = failure_time).
    ds = build_dataset([(_failure_scenario(), 1)], horizon=_HORIZON, step=timedelta(hours=12))
    start = _failure_scenario().start_utc
    failure = start + timedelta(hours=60)
    assert all(s.reference_time <= failure for s in ds.samples)


def test_failure_run_hat_beide_klassen() -> None:
    ds = build_dataset([(_failure_scenario(), 1)], horizon=_HORIZON, step=timedelta(hours=12))
    labels = {s.label for s in ds.samples}
    assert labels == {0, 1}


def test_healthy_szenario_nur_negative() -> None:
    ds = build_dataset([(_healthy_scenario(), 1)], horizon=_HORIZON, step=timedelta(hours=12))
    assert ds.samples  # nicht leer
    assert all(s.label == 0 for s in ds.samples)


def test_klassenbalance_wird_berichtet() -> None:
    ds = build_dataset(
        [(_failure_scenario(), 1), (_healthy_scenario(), 1)],
        horizon=_HORIZON,
        step=timedelta(hours=12),
    )
    n_neg, n_pos = ds.class_balance()
    assert n_neg > 0 and n_pos > 0
    assert n_neg + n_pos == len(ds.samples)


def test_feature_names_sind_sortierte_union() -> None:
    ds = build_dataset([(_failure_scenario(), 1)], horizon=_HORIZON, step=timedelta(hours=12))
    assert ds.feature_names
    assert list(ds.feature_names) == sorted(ds.feature_names)
    # Drift-Feature ist als Spalte präsent (Drift-Output als Feature).
    assert "drift__count" in ds.feature_names


# --------------------------------------------------------------------------- #
#  Lauf-disjunkter Split (Anti-Leakage)
# --------------------------------------------------------------------------- #
def test_split_ist_lauf_disjunkt() -> None:
    scn = _failure_scenario()
    healthy = _healthy_scenario()
    ds = build_dataset(
        [(scn, 1), (scn, 2), (healthy, 1), (healthy, 2)],
        horizon=_HORIZON,
        step=timedelta(hours=12),
    )
    train, evalset = split_by_seed(ds, holdout_seeds={2})
    train_runs = {s.run_id for s in train.samples}
    eval_runs = {s.run_id for s in evalset.samples}
    assert train_runs and eval_runs
    assert train_runs.isdisjoint(eval_runs)  # KEIN Lauf in beiden Splits
    assert all(s.seed == 2 for s in evalset.samples)
    assert all(s.seed == 1 for s in train.samples)


# --------------------------------------------------------------------------- #
#  Bucket-Konsistenz-Invarianten Training↔Inferenz (Fail-fast)
# --------------------------------------------------------------------------- #
def test_sub_minuten_intervall_wird_abgelehnt() -> None:
    # sample_interval < 1 Minute bricht die readings_1m-Bucket-Äquivalenz (time_bucket
    # '1 minute' vs. Minuten-Floor) → laut scheitern statt stillem Train/Serve-Skew.
    data = _failure_scenario_dict()
    data["scenario"]["sample_interval"] = "90s"
    with pytest.raises(ValueError, match="Minuten-Vielfaches"):
        build_dataset([(Scenario.model_validate(data), 1)], horizon=_HORIZON)


def test_startsekunde_ungleich_null_wird_abgelehnt() -> None:
    data = _failure_scenario_dict()
    data["scenario"]["start"] = "2026-03-02T00:00:30+00:00"
    with pytest.raises(ValueError, match="voller Minute"):
        build_dataset([(Scenario.model_validate(data), 1)], horizon=_HORIZON)


def test_quality_im_failure_szenario_wird_abgelehnt() -> None:
    # Quality-Missing wird im Trainingspfad nicht gespiegelt (Adapter lässt Buckets aus)
    # → divergente __n/__slope/__roc. Quality-freie Failure-Szenarien sind Pflicht.
    data = _failure_scenario_dict()
    data["data_points"][1]["quality"] = {"missing_probability": 0.1}
    with pytest.raises(ValueError, match="quality"):
        build_dataset([(Scenario.model_validate(data), 1)], horizon=_HORIZON)


def test_matrix_und_labels_konsistent() -> None:
    ds = build_dataset([(_failure_scenario(), 1)], horizon=_HORIZON, step=timedelta(hours=12))
    matrix, labels, groups = ds.matrix()
    assert len(matrix) == len(labels) == len(groups) == len(ds.samples)
    assert all(len(row) == len(ds.feature_names) for row in matrix)
