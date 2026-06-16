# ============================================================
#  FOREMAN — tests/reasoners/failure/test_recommendation_grounding.py
#  Zweck: Grounding-Quellen der Werker-Empfehlung (F-REC, Baustein 2). Geprüft wird
#         die zentrale Sicherheits-Invariante: Vorhersage + SHAP-Faktoren sind
#         `trusted=True` (modell-autoritativ, strukturiert), NEXUS-Recall ist
#         `trusted=False` (Substrat-Freitext); die autoritativen Zahlen stehen im
#         trusted-Content (Beleg-Basis für den numerischen Post-Check, Invariante I);
#         das source_id-Schema (pred:/factor:/recall:) ist korrekt.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime

from foreman.reasoners.event_chain.recall import RecallItem
from foreman.reasoners.failure.grounding import (
    _num,
    allowed_source_ids,
    build_recommendation_sources,
)
from foreman.reasoners.failure.schema import FailurePredictionRead, TopFactor

_REF = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)


def _prediction(**overrides: object) -> FailurePredictionRead:
    base: dict[str, object] = {
        "id": 1,
        "machine_id": 7,
        "reference_time": _REF,
        "horizon_h": 336,
        "probability": 0.87,
        "decision_threshold": 0.5,
        "decision": "elevated_risk",
        "top_factors": [
            TopFactor(
                feature="vibration_rms_velocity_spindle_bearing",
                value=3.9,
                shap=0.42,
                direction="increases_risk",
            ),
            TopFactor(
                feature="bearing_temperature_spindle",
                value=61.0,
                shap=0.18,
                direction="increases_risk",
            ),
        ],
        "validation_status": "simulation_only",
        "data_regime": "simulation",
        "model_version": "failure_lgbm@test",
        "created_at": _REF,
    }
    base.update(overrides)
    return FailurePredictionRead(**base)  # type: ignore[arg-type]


def test_vorhersage_und_faktoren_sind_trusted() -> None:
    sources = build_recommendation_sources(_prediction(), [])
    by_id = {s.source_id: s for s in sources}
    # Vorhersage-Quelle: modell-autoritativ, strukturiert → trusted.
    assert by_id["pred:1"].trusted is True
    # Faktor-Quellen: ebenfalls trusted (strukturierte SHAP-Attribution).
    factor_ids = [sid for sid in by_id if sid.startswith("factor:")]
    assert len(factor_ids) == 2
    assert all(by_id[fid].trusted is True for fid in factor_ids)


def test_autoritative_zahlen_im_trusted_content() -> None:
    # Invariante I-Basis: probability + horizon stehen im trusted-Content, damit der
    # Grounding-Post-Check sie als belegt zählt (das LLM darf sie zitieren).
    sources = build_recommendation_sources(_prediction(), [])
    pred_content = next(s.content for s in sources if s.source_id == "pred:1")
    assert "0.87" in pred_content
    assert "336" in pred_content


def test_recall_treffer_sind_untrusted() -> None:
    items = [RecallItem(content="Damals Lager getauscht"), RecallItem(content="Spindel heiß")]
    sources = build_recommendation_sources(_prediction(), items)
    recall_sources = [s for s in sources if s.source_id.startswith("recall:")]
    assert len(recall_sources) == 2
    assert all(s.trusted is False for s in recall_sources)
    assert recall_sources[0].source_id == "recall:0"


def test_allowed_source_ids_enthaelt_alle_quellen() -> None:
    items = [RecallItem(content="x")]
    sources = build_recommendation_sources(_prediction(), items)
    allowed = allowed_source_ids(sources)
    assert "pred:1" in allowed
    assert "recall:0" in allowed
    assert any(a.startswith("factor:") for a in allowed)


def test_num_nutzt_keine_wissenschaftliche_notation() -> None:
    # Der Gateway-Post-Check (§13.3) zerlegt Zahlen mit \d+(?:[.,]\d+)? und kennt kein
    # 'e' — '1e-05' würde in '1'/'05' zerfallen und eine belegte Zahl fälschlich als
    # unbelegt (bzw. zerlegte Mantissen-Ziffern als belegt) werten. _num bleibt Fixkomma.
    assert "e" not in _num(0.00001).lower()
    assert "e" not in _num(1e-7).lower()
    assert "e" not in _num(1_234_567.0).lower()
    # Normale Werte bleiben kompakt + kanonisch.
    assert _num(61.0) == "61"
    assert _num(3.9) == "3.9"
    assert _num(0.87) == "0.87"
    assert _num(0.0) == "0"
