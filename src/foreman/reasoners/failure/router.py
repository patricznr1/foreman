# ============================================================
#  FOREMAN — reasoners/failure/router.py
#  Zweck: HTTP-Routen des Ausfallvorhersage-Reasoners (F-PRED) unter
#         /api/v1/reasoners/failure/: on-demand Vorhersage (POST) + Abruf
#         persistierter Vorhersagen (GET).
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). BEWUSST on-demand: KEIN
#         Auto-Predict (Konsistenz mit F6, §14.3). KEINE Aktorik — der Reasoner
#         empfiehlt, schaltet nichts.
#  Auth: alle /api/v1-Routen liegen hinter der AuthMiddleware; POST verlangt
#         zusätzlich einen authentifizierten Operator.
#  Ehrlichkeit (§16): Jede Antwort (FailurePredictionRead) führt den Sim-Vorbehalt
#         (validation_status/data_regime/model_version) mit.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import CurrentUser, FailureModelDep, SessionDep
from foreman.db.models import FailurePredictionRecord
from foreman.reasoners.failure.schema import FailurePredictionRead, PredictRequest
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
