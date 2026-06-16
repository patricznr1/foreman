# ============================================================
#  FOREMAN — reasoners/failure/router.py
#  Zweck: HTTP-Routen des Ausfallvorhersage-Reasoners (F-PRED) + des Erklär-Layers
#         (F-REC) unter /api/v1/reasoners/failure/: on-demand Vorhersage (POST) +
#         Abruf persistierter Vorhersagen (GET); on-demand LLM-Werker-Empfehlung
#         zu einer Vorhersage (POST) + Abruf (GET).
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). BEWUSST on-demand: KEIN
#         Auto-Predict / KEIN Auto-LLM (Konsistenz mit F6, §14.3). KEINE Aktorik —
#         der Reasoner empfiehlt, schaltet nichts.
#  Auth: alle /api/v1-Routen liegen hinter der AuthMiddleware; POST verlangt
#         zusätzlich einen authentifizierten Operator (LLM-Kostenschutz).
#  Ehrlichkeit (§16): Jede Antwort führt den Sim-Vorbehalt mit
#         (validation_status/data_regime/model_version; bei F-REC zusätzlich der
#         deterministische validation_caveat).
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import (
    CurrentUser,
    FailureModelDep,
    GatewayDep,
    SessionDep,
    SubstrateClientDep,
)
from foreman.db.models import FailurePredictionRecord, FailureRecommendationRecord
from foreman.reasoners.failure.recommendation import (
    NumericGroundingError,
    PredictionNotFoundError,
    RecommendationOverclaimError,
    RecommendationService,
)
from foreman.reasoners.failure.schema import (
    FailurePredictionRead,
    PredictRequest,
    WorkerRecommendationRead,
)
from foreman.reasoners.failure.service import FailureService, MachineNotFoundError

router = APIRouter(prefix="/reasoners/failure", tags=["failure"])


@router.post(
    "/predict",
    response_model=FailurePredictionRead,
    status_code=status.HTTP_201_CREATED,
)
async def predict_failure(
    payload: PredictRequest,
    session: SessionDep,
    model: FailureModelDep,
    current_user: CurrentUser,
) -> FailurePredictionRecord:
    """Erzeugt on-demand eine Ausfallvorhersage für eine Maschine und persistiert sie.
    404, wenn die Maschine nicht existiert."""
    service = FailureService(session=session, model=model)
    lookback = (
        timedelta(hours=payload.lookback_hours) if payload.lookback_hours is not None else None
    )
    try:
        return await service.predict(
            payload.machine_id, reference_time=payload.reference_time, lookback=lookback
        )
    except MachineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Maschine nicht gefunden"
        ) from exc


@router.get("/predictions", response_model=list[FailurePredictionRead])
async def list_predictions(
    session: SessionDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Sequence[FailurePredictionRecord]:
    """Listet persistierte Ausfallvorhersagen (jüngste zuerst)."""
    stmt = select(FailurePredictionRecord).order_by(FailurePredictionRecord.created_at.desc())
    if machine_id is not None:
        stmt = stmt.where(FailurePredictionRecord.machine_id == machine_id)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/predictions/{prediction_id}", response_model=FailurePredictionRead)
async def get_prediction(prediction_id: int, session: SessionDep) -> FailurePredictionRecord:
    """Liefert eine einzelne persistierte Vorhersage. 404, wenn nicht vorhanden."""
    record = await session.get(FailurePredictionRecord, prediction_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vorhersage nicht gefunden"
        )
    return record


# --- F-REC: LLM-Werker-Empfehlung (Erklär-Layer über der Vorhersage) ---


@router.post(
    "/predictions/{prediction_id}/recommendation",
    response_model=WorkerRecommendationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_recommendation(
    prediction_id: int,
    session: SessionDep,
    gateway: GatewayDep,
    substrate: SubstrateClientDep,
    current_user: CurrentUser,
) -> FailureRecommendationRecord:
    """Erzeugt on-demand eine LLM-Werker-Empfehlung zu einer Vorhersage und persistiert sie.

    404, wenn die Vorhersage nicht existiert. 422, wenn die erzeugte Empfehlung den
    Grounding-/Vorbehalts-Guard nicht besteht (unbelegte Zahl — Invariante I — bzw.
    Umdeutung des Sim-Vorbehalts — Invariante II); in dem Fall wird NICHTS persistiert.
    KEIN Auto-LLM (on-demand, Kostenkontrolle). KEINE Aktorik."""
    service = RecommendationService(session=session, gateway=gateway, substrate=substrate)
    try:
        return await service.recommend(prediction_id)
    except PredictionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vorhersage nicht gefunden"
        ) from exc
    except (NumericGroundingError, RecommendationOverclaimError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Empfehlung verworfen: Grounding-/Vorbehalts-Guard nicht bestanden",
        ) from exc


@router.get("/predictions/{prediction_id}/recommendation", response_model=WorkerRecommendationRead)
async def get_recommendation(
    prediction_id: int, session: SessionDep
) -> FailureRecommendationRecord:
    """Liefert die jüngste persistierte Empfehlung zu einer Vorhersage. 404, wenn keine."""
    stmt = (
        select(FailureRecommendationRecord)
        .where(FailureRecommendationRecord.prediction_id == prediction_id)
        .order_by(FailureRecommendationRecord.created_at.desc())
        .limit(1)
    )
    record = (await session.scalars(stmt)).first()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Empfehlung nicht gefunden"
        )
    return record
