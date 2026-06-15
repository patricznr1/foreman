# ============================================================
#  FOREMAN — reasoners/event_chain/router.py
#  Zweck: HTTP-Routen des Ereignisketten-Reasoners (F6, Baustein 7) unter
#         /api/v1/reasoners/event_chain/: on-demand Rekonstruktion (POST) +
#         Abruf gespeicherter Erklärungen (GET).
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). BEWUSST on-demand: KEIN
#         automatischer LLM-Call pro Drift-Alarm (kostenkontrollierter LLM-Einsatz,
#         Brief §2.6). Der alarm-getriebene Hook bleibt als saubere Aufruf-Stelle
#         offen, wird hier aber nicht verdrahtet.
#  Auth: alle /api/v1-Routen liegen hinter der AuthMiddleware; POST verlangt
#         zusätzlich einen authentifizierten Operator (Kostenschutz). KEINE Aktorik.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import CurrentUser, GatewayDep, SessionDep, SubstrateClientDep
from foreman.db.models import ReasonerExplanationRecord
from foreman.reasoners.event_chain.schema import (
    ReasonerExplanationRead,
    ReconstructRequest,
)
from foreman.reasoners.event_chain.service import AnchorNotFoundError, EventChainService

router = APIRouter(prefix="/reasoners/event_chain", tags=["event_chain"])


@router.post(
    "/reconstruct",
    response_model=ReasonerExplanationRead,
    status_code=status.HTTP_201_CREATED,
)
async def reconstruct_event_chain(
    payload: ReconstructRequest,
    session: SessionDep,
    gateway: GatewayDep,
    substrate: SubstrateClientDep,
    current_user: CurrentUser,
) -> ReasonerExplanationRecord:
    """Rekonstruiert on-demand die Ereigniskette um einen Anker-Alarm und
    persistiert die gegroundete Erklärung. 404, wenn der Anker nicht existiert."""
    service = EventChainService(session=session, gateway=gateway, substrate=substrate)
    lookback = (
        timedelta(hours=payload.lookback_hours) if payload.lookback_hours is not None else None
    )
    try:
        return await service.reconstruct(payload.anchor_alarm_id, lookback=lookback)
    except AnchorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Anker-Alarm nicht gefunden"
        ) from exc


@router.get("/explanations", response_model=list[ReasonerExplanationRead])
async def list_explanations(
    session: SessionDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Sequence[ReasonerExplanationRecord]:
    """Listet gespeicherte Ereignisketten-Erklärungen (jüngste zuerst)."""
    stmt = select(ReasonerExplanationRecord).order_by(ReasonerExplanationRecord.created_at.desc())
    if machine_id is not None:
        stmt = stmt.where(ReasonerExplanationRecord.machine_id == machine_id)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/explanations/{explanation_id}", response_model=ReasonerExplanationRead)
async def get_explanation(explanation_id: int, session: SessionDep) -> ReasonerExplanationRecord:
    """Liefert eine einzelne gespeicherte Erklärung. 404, wenn nicht vorhanden."""
    record = await session.get(ReasonerExplanationRecord, explanation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Erklärung nicht gefunden"
        )
    return record
