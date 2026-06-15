# ============================================================
#  FOREMAN — tests/reasoners/failure/test_schema.py
#  Zweck: Pflicht-Test-Block für das FailurePrediction-Schema (F-PRED) — der
#         strukturelle Ehrlichkeits-Anker. Kern: validation_status ist Pflicht
#         und nicht umgehbar (kein Default, nur 'simulation_only'); die
#         Konsistenz decision↔threshold und tz-aware reference_time werden
#         erzwungen.
#  Architektur-Einordnung: Quality Gate §10.3 (Eingabe-/Edge-Validierung).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from foreman.reasoners.failure.schema import (
    FailurePrediction,
    TopFactor,
)

_REF = datetime(2026, 3, 20, 6, 0, tzinfo=UTC)


def _factor() -> TopFactor:
    return TopFactor(
        feature="vibration_rms_velocity_spindle_bearing__slope_24h",
        value=0.42,
        shap=0.61,
        direction="increases_risk",
    )


def _prediction(**overrides: object) -> FailurePrediction:
    base: dict[str, object] = {
        "machine_id": 1,
        "reference_time": _REF,
        "horizon_h": 336,
        "probability": 0.82,
        "decision_threshold": 0.5,
        "decision": "elevated_risk",
        "top_factors": (_factor(),),
        "validation_status": "simulation_only",
        "data_regime": "simulation",
        "model_version": "lgbm-failure-2026.06",
    }
    base.update(overrides)
    return FailurePrediction(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
#  Strukturelle Ehrlichkeit — validation_status ist Pflicht und nicht umgehbar
# --------------------------------------------------------------------------- #
def test_failure_prediction_ohne_validation_status_wird_abgelehnt() -> None:
    # Kern-Deliverable: eine Vorhersage kann NICHT ohne ihren Vorbehalt existieren.
    payload: dict[str, object] = {
        "machine_id": 1,
        "reference_time": _REF,
        "horizon_h": 336,
        "probability": 0.82,
        "decision_threshold": 0.5,
        "decision": "elevated_risk",
        "top_factors": (_factor(),),
        "data_regime": "simulation",
        "model_version": "lgbm-failure-2026.06",
    }
    with pytest.raises(ValidationError):
        FailurePrediction(**payload)  # type: ignore[arg-type]


def test_validation_status_nur_simulation_only() -> None:
    # Kein anderer Wert ist konstruierbar — auch nicht 'production' o. ä.
    with pytest.raises(ValidationError):
        _prediction(validation_status="production")


def test_failure_prediction_happy_path_ist_frozen() -> None:
    pred = _prediction()
    assert pred.validation_status == "simulation_only"
    assert pred.data_regime == "simulation"
    assert pred.probability == 0.82
    assert pred.decision == "elevated_risk"
    assert pred.top_factors[0].direction == "increases_risk"
    with pytest.raises(ValidationError):
        pred.probability = 0.1  # type: ignore[misc]


def test_failure_prediction_verbietet_zusatzfelder() -> None:
    with pytest.raises(ValidationError):
        _prediction(unexpected="schmuggel")


# --------------------------------------------------------------------------- #
#  Konsistenz-Invarianten
# --------------------------------------------------------------------------- #
def test_decision_muss_zu_threshold_passen() -> None:
    # probability >= threshold, aber decision='normal' → inkonsistent.
    with pytest.raises(ValidationError):
        _prediction(probability=0.9, decision_threshold=0.5, decision="normal")


def test_decision_normal_bei_niedriger_probability() -> None:
    pred = _prediction(probability=0.2, decision_threshold=0.5, decision="normal")
    assert pred.decision == "normal"


def test_reference_time_muss_tz_aware_sein() -> None:
    with pytest.raises(ValidationError):
        _prediction(reference_time=datetime(2026, 3, 20, 6, 0))


def test_probability_ausserhalb_0_1_wird_abgelehnt() -> None:
    with pytest.raises(ValidationError):
        _prediction(probability=1.5)


def test_horizon_muss_positiv_sein() -> None:
    with pytest.raises(ValidationError):
        _prediction(horizon_h=0)


def test_top_factor_direction_enum_streng() -> None:
    with pytest.raises(ValidationError):
        TopFactor(feature="x", value=1.0, shap=0.5, direction="hoch")  # type: ignore[arg-type]
