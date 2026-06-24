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
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import GatewayDep, SessionDep, SubstrateClientDep, require_roles
from foreman.db.models import ReasonerExplanationRecord, User
from foreman.realtime.authz import ROLE_MANAGER, ROLE_SHIFT_LEAD
from foreman.reasoners.event_chain.schema import (
    ReasonerExplanationDetailRead,
    ReasonerExplanationRead,
    ReconstructRequest,
    SiblingReference,
)
from foreman.reasoners.event_chain.service import AnchorNotFoundError, EventChainService

router = APIRouter(prefix="/reasoners/event_chain", tags=["event_chain"])

# Rekonstruktion ist ein On-Demand-Trigger (§21.15): Schichtleiter/Manager dürfen
# anstoßen, Werker/Techniker lesen nur. SERVERSEITIG erzwungen (§21.18).
TriggerUser = Annotated[User, Depends(require_roles(ROLE_SHIFT_LEAD, ROLE_MANAGER))]


@router.post(
    "/reconstruct",
    response_model=ReasonerExplanationDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def reconstruct_event_chain(
    payload: ReconstructRequest,
    session: SessionDep,
    gateway: GatewayDep,
    substrate: SubstrateClientDep,
    current_user: TriggerUser,
) -> ReasonerExplanationDetailRead:
    """Rekonstruiert on-demand die Ereigniskette um einen Anker-Alarm und
    persistiert die gegroundete Erklärung. Liefert die eingefrorene Kette + die
    ehrlichen Schwester-Referenzen mit. 404, wenn der Anker nicht existiert."""
    service = EventChainService(session=session, gateway=gateway, substrate=substrate)
    lookback = (
        timedelta(hours=payload.lookback_hours) if payload.lookback_hours is not None else None
    )
    try:
        record = await service.reconstruct(payload.anchor_alarm_id, lookback=lookback)
    except AnchorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Anker-Alarm nicht gefunden"
        ) from exc
    return ReasonerExplanationDetailRead.from_record(record)


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


@router.get("/explanations/{explanation_id}", response_model=ReasonerExplanationDetailRead)
async def get_explanation(
    explanation_id: int, session: SessionDep
) -> ReasonerExplanationDetailRead:
    """Liefert eine einzelne gespeicherte Erklärung inkl. eingefrorener Kette +
    Schwester-Referenzen (aus dem Snapshot, nie neu abgeleitet). 404, wenn fehlt."""
    record = await session.get(ReasonerExplanationRecord, explanation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Erklärung nicht gefunden"
        )
    return ReasonerExplanationDetailRead.from_record(record)


@router.get(
    "/explanations/{explanation_id}/siblings",
    response_model=list[SiblingReference],
)
async def get_explanation_siblings(
    explanation_id: int, session: SessionDep
) -> list[SiblingReference]:
    """Liefert die EINGEFRORENEN Schwester-Referenzen einer gespeicherten Erklärung
    (ehrlich aus realen Recall-Treffern, §21-D). Keine → leere Liste (kein Fake).
    404, wenn die Erklärung nicht existiert."""
    record = await session.get(ReasonerExplanationRecord, explanation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Erklärung nicht gefunden"
        )
    return [SiblingReference.model_validate(item) for item in (record.siblings_snapshot or [])]
