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
#  Maschinen-Scope (§20.4): Vorhersagen und Empfehlungen folgen der Sichtbarkeit
#         ihrer Maschine. Die Rollenfrage („darf anstoßen") und die Scope-Frage
#         („darf DIESE Maschine") sind zwei Prüfungen; die eine ersetzt die andere
#         nicht — ein Schichtleiter darf anstoßen, aber nur auf seinen Linien.
#  Ehrlichkeit (§16): Jede Antwort führt den Sim-Vorbehalt mit
#         (validation_status/data_regime/model_version; bei F-REC zusätzlich der
#         deterministische validation_caveat).
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.api.deps import (
    FailureModelDep,
    GatewayDep,
    MachineScope,
    MachineScopeDep,
    SessionDep,
    SubstrateClientDep,
    require_roles,
)
from foreman.db.models import FailurePredictionRecord, FailureRecommendationRecord, User
from foreman.realtime.authz import ROLE_MANAGER, ROLE_SHIFT_LEAD
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

# Vorhersage/Empfehlung sind On-Demand-Trigger (§21.10): Schichtleiter/Manager dürfen
# anstoßen, Werker/Techniker lesen nur. SERVERSEITIG erzwungen (§21.18).
TriggerUser = Annotated[User, Depends(require_roles(ROLE_SHIFT_LEAD, ROLE_MANAGER))]


async def _sichtbare_vorhersage(
    session: AsyncSession, scope: MachineScope, prediction_id: int
) -> FailurePredictionRecord:
    """Lädt eine Vorhersage, die im Ausschnitt des Anfragenden liegt — sonst 404.

    EINE Stelle für die drei Wege, die über eine `prediction_id` hereinkommen:
    Einzelabruf, Empfehlung erzeugen, Empfehlung lesen. Getrennte Prüfungen wären
    die Stelle, an der einer der drei zurückbliebe — und die Empfehlungs-Routen
    tragen keine eigene Maschinen-Kennung, an der es auffiele.

    Fremde und unbekannte Kennung enden gleich: Ein 403 würde bestätigen, dass die
    Vorhersage existiert.
    """
    record = await session.get(FailurePredictionRecord, prediction_id)
    if record is None or not await scope.can_see(record.machine_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vorhersage nicht gefunden"
        )
    return record


@router.post(
    "/predict",
    response_model=FailurePredictionRead,
    status_code=status.HTTP_201_CREATED,
)
async def predict_failure(
    payload: PredictRequest,
    session: SessionDep,
    model: FailureModelDep,
    current_user: TriggerUser,
    scope: MachineScopeDep,
) -> FailurePredictionRecord:
    """Erzeugt on-demand eine Ausfallvorhersage für eine Maschine und persistiert sie.
    403 außerhalb des eigenen Maschinen-Ausschnitts, 404, wenn die Maschine nicht existiert."""
    # Die Kennung kommt aus dem Rumpf, nicht aus dem Pfad — geprüft wird sie deshalb
    # genauso, nur an anderer Stelle.
    await scope.require(payload.machine_id)
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
    scope: MachineScopeDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Sequence[FailurePredictionRecord]:
    """Listet persistierte Ausfallvorhersagen im Maschinen-Ausschnitt (jüngste zuerst)."""
    stmt = await scope.limit_to(
        select(FailurePredictionRecord).order_by(FailurePredictionRecord.created_at.desc()),
        FailurePredictionRecord.machine_id,
        machine_id=machine_id,
    )
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/predictions/{prediction_id}", response_model=FailurePredictionRead)
async def get_prediction(
    prediction_id: int, session: SessionDep, scope: MachineScopeDep
) -> FailurePredictionRecord:
    """Liefert eine einzelne persistierte Vorhersage. 404, wenn nicht im Ausschnitt."""
    return await _sichtbare_vorhersage(session, scope, prediction_id)


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
    current_user: TriggerUser,
    scope: MachineScopeDep,
) -> FailureRecommendationRecord:
    """Erzeugt on-demand eine LLM-Werker-Empfehlung zu einer Vorhersage und persistiert sie.

    404, wenn die Vorhersage nicht existiert. 422, wenn die erzeugte Empfehlung den
    Grounding-/Vorbehalts-Guard nicht besteht (unbelegte Zahl — Invariante I — bzw.
    Umdeutung des Sim-Vorbehalts — Invariante II); in dem Fall wird NICHTS persistiert.
    KEIN Auto-LLM (on-demand, Kostenkontrolle). KEINE Aktorik."""
    await _sichtbare_vorhersage(session, scope, prediction_id)
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
    prediction_id: int, session: SessionDep, scope: MachineScopeDep
) -> FailureRecommendationRecord:
    """Liefert die jüngste persistierte Empfehlung zu einer Vorhersage. 404, wenn keine.

    Die Empfehlung trägt keine eigene Maschinen-Kennung — sie erbt den Ausschnitt
    ihrer Vorhersage, sonst wäre sie der offene Nebeneingang zu ihr.
    """
    await _sichtbare_vorhersage(session, scope, prediction_id)
    stmt = (
        select(FailureRecommendationRecord)
        .where(FailureRecommendationRecord.prediction_id == prediction_id)
        # id.desc() als Tiebreaker: bei gleichem created_at bleibt „die jüngste"
        # deterministisch (die zuletzt eingefügte Zeile).
        .order_by(
            FailureRecommendationRecord.created_at.desc(),
            FailureRecommendationRecord.id.desc(),
        )
        .limit(1)
    )
    record = (await session.scalars(stmt)).first()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Empfehlung nicht gefunden"
        )
    return record
