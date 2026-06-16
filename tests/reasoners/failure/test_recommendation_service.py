# ============================================================
#  FOREMAN — tests/reasoners/failure/test_recommendation_service.py
#  Zweck: Pflicht-Test-Block der F-REC-Pipeline E2E gegen die ECHTE TimescaleDB
#         (Gateway über das echte LiteLLMGateway + Mock-Backend, Substrat aus).
#  KERN-AKZEPTANZ: validation_caveat ist IMMER präsent und deterministisch; der
#         Sim-Vorbehalt (validation_status/data_regime/model_version) wird
#         mitgeführt; die autoritativen Zahlen (probability/horizon/decision) werden
#         aus der Vorhersage geerbt; erfundene Zitate werden nicht referenziert;
#         404-Pfad bei fehlender Vorhersage. Persistenz in failure_recommendations.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, echte DB).
# ============================================================
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import asyncpg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import FailurePredictionRecord, FailureRecommendationRecord, Machine
from foreman.llm import LiteLLMGateway
from foreman.reasoners.failure.recommendation import (
    PredictionNotFoundError,
    RecommendationService,
)
from foreman.reasoners.failure.schema import validation_caveat_for

pytestmark = pytest.mark.integration

_REF = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
_TOP_FACTORS: list[dict[str, object]] = [
    {
        "feature": "vibration_rms_velocity_spindle_bearing",
        "value": 3.9,
        "shap": 0.42,
        "direction": "increases_risk",
    },
    {
        "feature": "bearing_temperature_spindle",
        "value": 61.0,
        "shap": 0.18,
        "direction": "increases_risk",
    },
]


async def _seed_prediction(
    session: AsyncSession, *, probability: float = 0.87, decision: str = "elevated_risk"
) -> FailurePredictionRecord:
    """Seedet eine Maschine + eine persistierte FailurePrediction (ohne F-PRED-Pipeline)."""
    machine = Machine(label="BAZ-01", machine_class="cnc_machining_center")
    session.add(machine)
    await session.flush()
    record = FailurePredictionRecord(
        machine_id=machine.id,
        reference_time=_REF,
        horizon_h=336,
        probability=probability,
        decision_threshold=0.5,
        decision=decision,
        validation_status="simulation_only",
        data_regime="simulation",
        model_version="failure_lgbm@test",
        top_factors=_TOP_FACTORS,
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record


def _good_reply(prediction_id: int) -> str:
    """Belegte, zahl-arme Empfehlung, die Vorhersage + Faktor zitiert (kein Reject)."""
    return (
        f"Erhöhtes Ausfallrisiko [pred:{prediction_id}]: die steigende Lagervibration "
        f"[factor:vibration_rms_velocity_spindle_bearing] treibt das Risikosignal. "
        f"Empfehlung: das Spindellager bei der nächsten Schicht prüfen. Diese "
        f"Einschätzung beruht auf simulierten Verläufen und ist nicht validiert."
    )


async def test_empfehlung_traegt_immer_deterministischen_vorbehalt(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    pred = await _seed_prediction(db_session)
    service = RecommendationService(
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=_good_reply(pred.id))]),
    )
    record = await service.recommend(pred.id)

    # KERN-AKZEPTANZ (Invariante II): der Vorbehalt ist IMMER präsent + deterministisch.
    assert record.validation_caveat == validation_caveat_for("simulation_only")
    assert record.validation_status == "simulation_only"
    assert record.data_regime == "simulation"
    assert record.model_version == pred.model_version
    assert record.id is not None


async def test_empfehlung_erbt_autoritative_zahlen_und_persistiert(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    pred = await _seed_prediction(db_session)
    service = RecommendationService(
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=_good_reply(pred.id))]),
    )
    record = await service.recommend(pred.id)

    # Invariante I: die Zahlen stammen aus der Vorhersage (nie aus dem LLM).
    assert record.horizon_h == pred.horizon_h
    assert record.probability == pred.probability
    assert record.decision == pred.decision
    assert record.prediction_id == pred.id
    # Die Vorhersage-Quelle wird referenziert; referenced ⊆ allowed (Schema-Guard).
    assert f"pred:{pred.id}" in record.referenced_source_ids

    # tatsächlich in der DB?
    stored = (
        await db_session.scalars(
            select(FailureRecommendationRecord).where(
                FailureRecommendationRecord.prediction_id == pred.id
            )
        )
    ).all()
    assert len(stored) == 1


async def test_erfundene_quelle_wird_nicht_referenziert(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    pred = await _seed_prediction(db_session)
    reply = (
        f"Risiko [pred:{pred.id}] und eine erfundene Quelle [factor:erfunden]. "
        f"Empfehlung: Lager prüfen. Simulationsbasiert, nicht validiert."
    )
    service = RecommendationService(
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=reply)]),
    )
    record = await service.recommend(pred.id)
    assert f"pred:{pred.id}" in record.referenced_source_ids
    assert "factor:erfunden" not in record.referenced_source_ids


async def test_unbekannte_vorhersage_wirft(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    service = RecommendationService(
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply="x")]),
    )
    with pytest.raises(PredictionNotFoundError):
        await service.recommend(999_999)


async def test_db_check_erzwingt_sim_vorbehalt_im_caveat(raw_conn: asyncpg.Connection) -> None:
    # Defense-in-Depth: der Sim-Vorbehalt ist auch im CAVEAT-TEXT an der
    # PERSISTENZGRENZE gebunden — ein pydantic-umgehender Direkt-Insert mit
    # umgedeutetem Vorbehalt (ohne Sim-Marker) wird vom DB-CHECK abgewiesen.
    machine_id = await raw_conn.fetchval(
        "INSERT INTO machines (label, machine_class) VALUES ('M', 'cnc') RETURNING id"
    )
    prediction_id = await raw_conn.fetchval(
        "INSERT INTO failure_predictions "
        "(machine_id, reference_time, horizon_h, probability, decision_threshold, "
        "decision, validation_status, data_regime, model_version, top_factors) "
        "VALUES ($1, now(), 336, 0.5, 0.5, 'normal', 'simulation_only', 'simulation', "
        "'v', '[]'::jsonb) RETURNING id",
        machine_id,
    )
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await raw_conn.execute(
            "INSERT INTO failure_recommendations "
            "(prediction_id, machine_id, recommendation_text, validation_caveat, "
            "validation_status, data_regime, model_version, referenced_source_ids, "
            "horizon_h, probability, decision) "
            "VALUES ($1, $2, 'x', 'Diese Prognose ist real validiert und gesichert.', "
            "'simulation_only', 'simulation', 'v', '[]'::jsonb, 336, 0.5, 'normal')",
            prediction_id,
            machine_id,
        )
