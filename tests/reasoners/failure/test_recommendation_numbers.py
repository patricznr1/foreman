# ============================================================
#  FOREMAN — tests/reasoners/failure/test_recommendation_numbers.py
#  Zweck: Invariante I (Zahlen autoritativ vom Modell). Führt der LLM-Text eine
#         UNBELEGTE Zahl ein, greift der numerische Post-Check über den Gateway-
#         Grounding-Report → HARTER Reject (NumericGroundingError), KEINE Persistenz.
#         Belegte Zahlen (aus der trusted Vorhersage-Quelle) gehen durch.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, echte DB).
# ============================================================
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import FailurePredictionRecord, FailureRecommendationRecord, Machine
from foreman.llm import LiteLLMGateway
from foreman.reasoners.failure.recommendation import (
    NumericGroundingError,
    RecommendationService,
)

pytestmark = pytest.mark.integration

_REF = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
_TOP_FACTORS: list[dict[str, object]] = [
    {
        "feature": "vibration_rms_velocity_spindle_bearing",
        "value": 3.9,
        "shap": 0.42,
        "direction": "increases_risk",
    },
]


async def _seed_prediction(session: AsyncSession) -> FailurePredictionRecord:
    machine = Machine(label="BAZ-01", machine_class="cnc_machining_center")
    session.add(machine)
    await session.flush()
    record = FailurePredictionRecord(
        machine_id=machine.id,
        reference_time=_REF,
        horizon_h=336,
        probability=0.87,
        decision_threshold=0.5,
        decision="elevated_risk",
        validation_status="simulation_only",
        data_regime="simulation",
        model_version="failure_lgbm@test",
        top_factors=_TOP_FACTORS,
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record


async def test_erfundene_zahl_wird_rejected_und_nicht_persistiert(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    pred = await _seed_prediction(db_session)
    # Das LLM führt eine unbelegte, neuartige Zahl ein (999 steht in keiner trusted
    # Quelle: weder die Wahrscheinlichkeit 0.87 noch der Horizont 336).
    reply = f"Laut [pred:{pred.id}] fällt die Maschine in genau 999 Stunden aus. Lager prüfen."
    service = RecommendationService(
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=reply)]),
    )
    with pytest.raises(NumericGroundingError):
        await service.recommend(pred.id)

    # Invariante I: KEINE Empfehlung mit erfundener Zahl wird persistiert.
    stored = (await db_session.scalars(select(FailureRecommendationRecord))).all()
    assert list(stored) == []


async def test_belegte_zahlen_gehen_durch(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    pred = await _seed_prediction(db_session)
    # Wahrscheinlichkeit 0.87 + Horizont 336 stehen in der trusted pred-Quelle → belegt.
    reply = (
        f"[pred:{pred.id}]: Ausfallwahrscheinlichkeit 0.87 im Horizont von 336 Stunden. "
        f"Empfehlung: Lager prüfen. Simulationsbasiert, nicht validiert."
    )
    service = RecommendationService(
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=reply)]),
    )
    record = await service.recommend(pred.id)
    assert record.id is not None
    assert record.probability == pred.probability


async def test_grounding_disabled_rejectet_trotzdem(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    # FAIL-CLOSED (Invariante I): selbst wenn das Gateway-Grounding global
    # deaktiviert ist (FOREMAN_LLM_GROUNDING_ENABLED=false → response.grounding=None),
    # MUSS F-REC die erfundene Zahl selbst fangen und rejecten — der Hart-Reject darf
    # nicht an einer abschaltbaren Gateway-Policy hängen.
    pred = await _seed_prediction(db_session)
    reply = f"Laut [pred:{pred.id}] fällt die Maschine in genau 999 Stunden aus. Lager prüfen."
    service = RecommendationService(
        session=db_session,
        gateway=make_gateway(
            backends=[make_backend("local", reply=reply)], grounding_enabled=False
        ),
    )
    with pytest.raises(NumericGroundingError):
        await service.recommend(pred.id)
    stored = (await db_session.scalars(select(FailureRecommendationRecord))).all()
    assert list(stored) == []


async def test_grounding_strict_rejectet_als_numeric(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    # Im strict-Modus wirft das Gateway selbst GroundingViolation in complete().
    # F-REC behandelt das als denselben Invariante-I-Reject (NumericGroundingError),
    # nicht als unbehandelten 500 — konsistentes Reject-Verhalten + Metrik.
    pred = await _seed_prediction(db_session)
    reply = f"Laut [pred:{pred.id}] fällt die Maschine in genau 999 Stunden aus. Lager prüfen."
    service = RecommendationService(
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=reply)], grounding_strict=True),
    )
    with pytest.raises(NumericGroundingError):
        await service.recommend(pred.id)
    stored = (await db_session.scalars(select(FailureRecommendationRecord))).all()
    assert list(stored) == []
