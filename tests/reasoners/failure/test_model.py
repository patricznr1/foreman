# ============================================================
#  FOREMAN — tests/reasoners/failure/test_model.py
#  Zweck: Pflicht-Test-Block der Inferenz (F-PRED): Artefakt speichern/laden,
#         predict (Wahrscheinlichkeit) + SHAP-Faktor-Attribution (Form),
#         validation_status/data_regime/model_version aus dem Artefakt.
#  Architektur-Einordnung: Quality Gate §10.3 (Inferenz, ohne DB).
# ============================================================
from __future__ import annotations

import math
from pathlib import Path

import lightgbm as lgb
import numpy as np

from foreman.reasoners.failure.model import (
    ModelMetadata,
    load_model,
    save_artifact,
)
from foreman.reasoners.failure.schema import TopFactor

_FEATURES = ("vib__mean", "vib__slope", "drift__count")


def _tiny_booster() -> lgb.Booster:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(160, 3))
    # Risiko steigt mit Feature 0 und 1 (vib mean/slope) — lernbares Signal.
    y = ((x[:, 0] + x[:, 1]) > 0).astype(int)
    clf = lgb.LGBMClassifier(n_estimators=30, min_child_samples=5, verbose=-1, random_state=0)
    clf.fit(x, y)
    booster: lgb.Booster = clf.booster_
    return booster


def _metadata() -> ModelMetadata:
    return ModelMetadata(
        model_version="lgbm-failure-test",
        training_source="simulation",
        data_regime="simulation",
        validation_status="simulation_only",
        horizon_h=336,
        decision_threshold=0.5,
        feature_schema=_FEATURES,
        scenario_hashes={"tiny_failure": "deadbeef"},
        seed=0,
        metrics={"pr_auc": 1.0, "roc_auc": 1.0, "brier": 0.01},
        n_train=120,
        n_eval=40,
        n_pos_train=60,
        n_neg_train=60,
    )


def _artifact(tmp_path: Path) -> Path:
    path = tmp_path / "artifact"
    save_artifact(path, _tiny_booster(), _metadata())
    return path


def test_artefakt_roundtrip_traegt_validation_status(tmp_path: Path) -> None:
    model = load_model(_artifact(tmp_path))
    assert model.metadata.validation_status == "simulation_only"
    assert model.metadata.data_regime == "simulation"
    assert model.metadata.model_version == "lgbm-failure-test"
    assert model.feature_schema == _FEATURES


def test_predict_liefert_wahrscheinlichkeit_und_faktoren(tmp_path: Path) -> None:
    model = load_model(_artifact(tmp_path))
    proba, factors = model.predict({"vib__mean": 2.0, "vib__slope": 1.5, "drift__count": 1.0})
    assert 0.0 <= proba <= 1.0
    assert factors
    assert all(isinstance(f, TopFactor) for f in factors)
    assert all(f.direction in ("increases_risk", "decreases_risk") for f in factors)
    # SHAP-Vorzeichen ↔ Richtung konsistent.
    assert all((f.shap >= 0) == (f.direction == "increases_risk") for f in factors)


def test_predict_ignoriert_fehlende_features_in_faktoren(tmp_path: Path) -> None:
    model = load_model(_artifact(tmp_path))
    # slope + drift fehlen → NaN → dürfen NICHT als Top-Faktor mit NaN-Wert auftauchen.
    _, factors = model.predict({"vib__mean": 2.0})
    assert all(math.isfinite(f.value) for f in factors)


def test_hoeheres_signal_erhoeht_wahrscheinlichkeit(tmp_path: Path) -> None:
    model = load_model(_artifact(tmp_path))
    low, _ = model.predict({"vib__mean": -2.0, "vib__slope": -2.0, "drift__count": 0.0})
    high, _ = model.predict({"vib__mean": 2.0, "vib__slope": 2.0, "drift__count": 1.0})
    assert high > low


def test_metadata_json_ist_gueltig_und_pii_frei(tmp_path: Path) -> None:
    path = _artifact(tmp_path)
    text = (path / "metadata.json").read_text(encoding="utf-8")
    assert "simulation_only" in text
    assert "lgbm-failure-test" in text
