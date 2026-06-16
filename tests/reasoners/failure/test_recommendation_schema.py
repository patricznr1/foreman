# ============================================================
#  FOREMAN — tests/reasoners/failure/test_recommendation_schema.py
#  Zweck: Reine Schema-Invarianten der LLM-Werker-Empfehlung (F-REC) — die
#         Ehrlichkeit zuerst festgenagelt. Geprüft wird strukturell (ohne DB/LLM):
#         (II) der Sim-Vorbehalt ist deterministisch und NICHT durch LLM-Text
#              ersetzbar (validation_caveat == validation_caveat_for(status));
#              validation_status ist Pflichtfeld ohne Default.
#         (Output-Guard) referenced_source_ids ⊆ allowed_source_ids.
#  Architektur-Einordnung: Quality Gate §10.3 (reine Unit-Ebene).
# ============================================================
from __future__ import annotations

import pytest
from pydantic import ValidationError

from foreman.reasoners.failure.schema import (
    WorkerRecommendation,
    validation_caveat_for,
)


def _recommendation(**overrides: object) -> WorkerRecommendation:
    """Baut eine gültige WorkerRecommendation; einzelne Felder überschreibbar."""
    base: dict[str, object] = {
        "prediction_id": 1,
        "machine_id": 7,
        "recommendation_text": (
            "Erhöhtes Risiko an der Spindel [pred:1]; Lager prüfen [factor:vibration]."
        ),
        "validation_caveat": validation_caveat_for("simulation_only"),
        "validation_status": "simulation_only",
        "data_regime": "simulation",
        "model_version": "failure_lgbm@test",
        "referenced_source_ids": ("pred:1", "factor:vibration"),
        "allowed_source_ids": ("pred:1", "factor:vibration", "recall:0"),
        "horizon_h": 336,
        "probability": 0.87,
        "decision": "elevated_risk",
    }
    base.update(overrides)
    return WorkerRecommendation(**base)  # type: ignore[arg-type]


def test_validation_caveat_for_liefert_sim_satz() -> None:
    caveat = validation_caveat_for("simulation_only")
    assert "simul" in caveat.lower()
    assert len(caveat) > 0


def test_recommendation_traegt_deterministischen_vorbehalt() -> None:
    rec = _recommendation()
    # Invariante II: der Vorbehalt ist NICHT LLM-generiert, sondern der Soll-Satz.
    assert rec.validation_caveat == validation_caveat_for("simulation_only")
    assert rec.validation_status == "simulation_only"
    assert rec.data_regime == "simulation"


def test_abweichender_vorbehalt_wird_abgelehnt() -> None:
    # Invariante II: der Vorbehalt darf nicht durch beliebigen Text ersetzt werden.
    with pytest.raises(ValidationError):
        _recommendation(validation_caveat="Diese Prognose ist validiert und gesichert.")


def test_fehlender_validation_status_wirft() -> None:
    # validation_status ist Pflichtfeld ohne Default (struktureller Vorbehalt, §16).
    with pytest.raises(ValidationError):
        WorkerRecommendation(  # type: ignore[call-arg]
            prediction_id=1,
            machine_id=7,
            recommendation_text="x",
            validation_caveat=validation_caveat_for("simulation_only"),
            data_regime="simulation",
            model_version="v",
            referenced_source_ids=(),
            allowed_source_ids=(),
            horizon_h=1,
            probability=0.5,
            decision="normal",
        )


def test_referenced_muss_teilmenge_von_allowed_sein() -> None:
    # Output-Guard: ein erfundenes Zitat (nicht in der Whitelist) ist unzulässig.
    with pytest.raises(ValidationError):
        _recommendation(
            referenced_source_ids=("pred:1", "factor:erfunden"),
            allowed_source_ids=("pred:1",),
        )


def test_referenced_innerhalb_allowed_ok() -> None:
    rec = _recommendation(
        referenced_source_ids=("pred:1",),
        allowed_source_ids=("pred:1", "factor:vibration"),
    )
    assert rec.referenced_source_ids == ("pred:1",)
