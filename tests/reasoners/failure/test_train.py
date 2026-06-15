# ============================================================
#  FOREMAN — tests/reasoners/failure/test_train.py
#  Zweck: Pflicht-Test-Block des Offline-Trainings (F-PRED): Training-Smoke,
#         Artefakt + Metadaten (Quelle=simulation, Feature-Schema, Metriken,
#         Horizont), Seed-Determinismus, Ehrlichkeits-Banner im Trainings-Log.
#  Architektur-Einordnung: Quality Gate §10.3.
# ============================================================
from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from foreman.reasoners.failure.dataset import Sample, TrainingDataset, split_by_seed
from foreman.reasoners.failure.model import load_model
from foreman.reasoners.failure.train import main, train_and_evaluate, train_summary

_REF = datetime(2026, 3, 20, tzinfo=UTC)
_FEATURES = ("drift__count", "x__mean")


def _dataset() -> TrainingDataset:
    """Synthetischer, lernbarer Datensatz: x__mean korreliert mit dem Label."""
    rng = random.Random(0)
    samples: list[Sample] = []
    for seed in (1, 2, 3):
        for i in range(40):
            label = i % 2
            value = label + rng.gauss(0.0, 0.25)
            samples.append(
                Sample(
                    scenario="syn",
                    seed=seed,
                    reference_time=_REF + timedelta(hours=i),
                    features={"x__mean": value, "drift__count": float(label)},
                    label=label,
                )
            )
    return TrainingDataset(
        samples=tuple(samples), horizon=timedelta(days=14), feature_names=_FEATURES
    )


def _split() -> tuple[TrainingDataset, TrainingDataset]:
    return split_by_seed(_dataset(), holdout_seeds={3})


def test_training_liefert_artefakt_metadaten() -> None:
    train_ds, eval_ds = _split()
    booster, metadata = train_and_evaluate(
        train_ds,
        eval_ds,
        seed=42,
        model_version="lgbm-failure-test",
        scenario_hashes={"syn": "abc123"},
    )
    assert booster is not None
    assert metadata.training_source == "simulation"
    assert metadata.data_regime == "simulation"
    assert metadata.validation_status == "simulation_only"
    assert metadata.feature_schema == _FEATURES
    assert metadata.horizon_h == 336  # 14 Tage
    assert set(metadata.metrics) == {"pr_auc", "roc_auc", "brier"}
    assert metadata.scenario_hashes == {"syn": "abc123"}
    assert metadata.n_pos_train + metadata.n_neg_train == len(train_ds.samples)


def test_seed_determinismus() -> None:
    train_ds, eval_ds = _split()
    kw = {"seed": 7, "model_version": "v", "scenario_hashes": {"syn": "h"}}
    _, meta_a = train_and_evaluate(train_ds, eval_ds, **kw)  # type: ignore[arg-type]
    _, meta_b = train_and_evaluate(train_ds, eval_ds, **kw)  # type: ignore[arg-type]
    assert meta_a.metrics == meta_b.metrics
    assert meta_a.decision_threshold == meta_b.decision_threshold


def test_artefakt_speichern_und_laden(tmp_path: Path) -> None:
    from foreman.reasoners.failure.model import save_artifact

    train_ds, eval_ds = _split()
    booster, metadata = train_and_evaluate(
        train_ds, eval_ds, seed=1, model_version="v", scenario_hashes={"syn": "h"}
    )
    save_artifact(tmp_path / "art", booster, metadata)
    model = load_model(tmp_path / "art")
    proba, _factors = model.predict({"x__mean": 1.0, "drift__count": 1.0})
    assert 0.0 <= proba <= 1.0
    assert model.metadata.validation_status == "simulation_only"


def test_metriken_sind_endlich_und_im_bereich() -> None:
    train_ds, eval_ds = _split()
    _, metadata = train_and_evaluate(
        train_ds, eval_ds, seed=1, model_version="v", scenario_hashes={"syn": "h"}
    )
    assert 0.0 <= metadata.metrics["pr_auc"] <= 1.0
    assert 0.0 <= metadata.metrics["roc_auc"] <= 1.0
    assert 0.0 <= metadata.metrics["brier"] <= 1.0


def test_training_summary_traegt_ehrlichkeits_banner() -> None:
    _, metadata = train_and_evaluate(
        *_split(), seed=1, model_version="v", scenario_hashes={"syn": "h"}
    )
    summary = train_summary(metadata)
    # Metriken werden NIE als „Genauigkeit der Ausfallvorhersage" verkauft.
    assert "Funktionsnachweis" in summary
    assert "simulation_only" in summary
    assert "Realitätsnachweis" in summary


def test_einklassiger_eval_split_wirft() -> None:
    # Eval-Holdout nur Negative → keine aussagekräftige PR-/ROC-AUC. Lieber laut
    # scheitern als ein Artefakt mit NaN-Metriken speichern (das nicht mehr lädt).
    samples: list[Sample] = []
    label_plan = {1: [i % 2 for i in range(20)], 2: [i % 2 for i in range(20)], 3: [0] * 20}
    for seed, labels in label_plan.items():
        for i, label in enumerate(labels):
            samples.append(
                Sample(
                    scenario="syn",
                    seed=seed,
                    reference_time=_REF + timedelta(hours=i),
                    features={"x__mean": float(label), "drift__count": 0.0},
                    label=label,
                )
            )
    ds = TrainingDataset(
        samples=tuple(samples), horizon=timedelta(days=14), feature_names=_FEATURES
    )
    train, evalset = split_by_seed(ds, holdout_seeds={3})
    with pytest.raises(ValueError, match="einklassig"):
        train_and_evaluate(train, evalset, seed=1, model_version="v", scenario_hashes={"syn": "h"})


def test_cli_smoke_auf_echten_szenarien(tmp_path: Path) -> None:
    # End-to-End-Smoke des Offline-Trainings auf echten Szenarien (Brief: kleines
    # Szenario). Eval-Holdout enthält ein Failure- + ein Healthy-Szenario → beide
    # Klassen → endliche Metriken (kein NaN im Artefakt).
    out = tmp_path / "artifact"
    code = main(
        [
            "--scenarios",
            "lubrication_correlation,healthy_baseline",
            "--seeds",
            "1,2",
            "--holdout-seeds",
            "2",
            "--horizon-days",
            "14",
            "--step-hours",
            "24",
            "--seed",
            "7",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    model = load_model(out)
    assert model.metadata.validation_status == "simulation_only"
    assert model.metadata.training_source == "simulation"
    assert model.metadata.lookback_h == 72
    assert set(model.metadata.scenario_hashes) == {"lubrication_correlation", "healthy_baseline"}
    assert all(math.isfinite(value) for value in model.metadata.metrics.values())
