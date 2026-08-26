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
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.api.deps import (
    GatewayDep,
    ResourceScope,
    ResourceScopeDep,
    SessionDep,
    SubstrateClientDep,
    require_roles,
)
from foreman.db.models import Alarm, ReasonerExplanationRecord, User
from foreman.realtime.authz import ROLE_MANAGER, ROLE_SHIFT_LEAD
from foreman.reasoners.event_chain.schema import (
    ReasonerExplanationDetailRead,
    ReasonerExplanationRead,
    ReconstructRequest,
    SiblingReference,
    nur_sichtbare_geschwister,
)
from foreman.reasoners.event_chain.service import AnchorNotFoundError, EventChainService

router = APIRouter(prefix="/reasoners/event_chain", tags=["event_chain"])

# Rekonstruktion ist ein On-Demand-Trigger (§21.15): Schichtleiter/Manager dürfen
# anstoßen, Werker/Techniker lesen nur. SERVERSEITIG erzwungen (§21.18).
TriggerUser = Annotated[User, Depends(require_roles(ROLE_SHIFT_LEAD, ROLE_MANAGER))]


async def _sichtbare_erklaerung(
    session: AsyncSession, scope: ResourceScope, explanation_id: int
) -> ReasonerExplanationRecord:
    """Lädt eine Erklärung, die im Ausschnitt des Anfragenden liegt — sonst 404.

    EINE Stelle für beide Wege, die über eine `explanation_id` hereinkommen:
    Einzelabruf und Schwester-Referenzen. Getrennte Prüfungen wären die Stelle, an
    der einer der beiden zurückbliebe — und die Schwestern tragen keine eigene
    Maschinen-Kennung, an der es auffiele.

    Fremde und unbekannte Kennung enden gleich: Ein 403 würde bestätigen, dass die
    Erklärung existiert.
    """
    record = await session.get(ReasonerExplanationRecord, explanation_id)
    if record is None or not await scope.can_see(record.machine_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Erklärung nicht gefunden"
        )
    return record


async def _sichtbarer_anker(
    session: AsyncSession, scope: ResourceScope, anchor_alarm_id: int
) -> Alarm:
    """Lädt den Anker-Alarm, wenn er im Ausschnitt des Anfragenden liegt — sonst 404.

    Die Rolle allein entscheidet hier nicht: Ein Schichtleiter darf anstoßen, aber
    nur für Maschinen seiner Linien. Die Kennung kommt aus dem Rumpf und benennt
    einen Alarm, nicht die Maschine — der Ausschnitt hängt deshalb an dem, was der
    Anker über seine Maschine aussagt, und muss geprüft werden, BEVOR der Reasoner
    Alarme, Notizen und Wartungsereignisse dieser Maschine zusammenträgt.

    Fremde und unbekannte Kennung enden gleich, wie beim Einzelabruf eines Alarms:
    Ein 403 würde bestätigen, dass der Alarm existiert.
    """
    anchor = await session.get(Alarm, anchor_alarm_id)
    if anchor is None or not await scope.can_see(anchor.machine_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Anker-Alarm nicht gefunden"
        )
    return anchor


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
    scope: ResourceScopeDep,
) -> ReasonerExplanationDetailRead:
    """Rekonstruiert on-demand die Ereigniskette um einen Anker-Alarm und
    persistiert die gegroundete Erklärung. Liefert die eingefrorene Kette + die
    ehrlichen Schwester-Referenzen mit. 404, wenn der Anker nicht existiert oder
    außerhalb des Maschinen-Ausschnitts liegt."""
    # Vor dem Lauf, nicht danach: Der Reasoner liest Alarme, Werker-Notizen und
    # Wartungsereignisse der Anker-Maschine und persistiert die Erklärung. Eine
    # Prüfung erst auf dem Ergebnis käme zu spät — die Daten wären dann bereits
    # zusammengetragen und die Antwort trüge sie.
    await _sichtbarer_anker(session, scope, payload.anchor_alarm_id)
    # Der Ausschnitt geht MIT in den Reasoner: Sein Gedächtnis-Abruf sucht nach
    # Maschinenklasse und Signatur, nicht nach Maschine, und trägt deshalb Fälle
    # anderer Linien herein — in die Schwester-Referenzen wie in das, was das
    # Sprachmodell zu sehen bekommt.
    service = EventChainService(
        session=session,
        gateway=gateway,
        substrate=substrate,
        sichtbare_maschinen=await scope.machine_ids(),
    )
    lookback = (
        timedelta(hours=payload.lookback_hours) if payload.lookback_hours is not None else None
    )
    try:
        record = await service.reconstruct(payload.anchor_alarm_id, lookback=lookback)
    except AnchorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Anker-Alarm nicht gefunden"
        ) from exc
    return ReasonerExplanationDetailRead.from_record(
        record, sichtbare_maschinen=await scope.machine_ids()
    )


@router.get("/explanations", response_model=list[ReasonerExplanationRead])
async def list_explanations(
    session: SessionDep,
    scope: ResourceScopeDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Sequence[ReasonerExplanationRecord]:
    """Gespeicherte Ereignisketten-Erklärungen im Maschinen-Ausschnitt (jüngste zuerst)."""
    stmt = await scope.limit_to(
        select(ReasonerExplanationRecord).order_by(ReasonerExplanationRecord.created_at.desc()),
        ReasonerExplanationRecord.machine_id,
        machine_id=machine_id,
    )
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/explanations/{explanation_id}", response_model=ReasonerExplanationDetailRead)
async def get_explanation(
    explanation_id: int, session: SessionDep, scope: ResourceScopeDep
) -> ReasonerExplanationDetailRead:
    """Liefert eine einzelne gespeicherte Erklärung inkl. eingefrorener Kette +
    Schwester-Referenzen (aus dem Snapshot, nie neu abgeleitet). 404, wenn fehlt
    oder außerhalb des Maschinen-Ausschnitts liegt."""
    record = await _sichtbare_erklaerung(session, scope, explanation_id)
    return ReasonerExplanationDetailRead.from_record(
        record, sichtbare_maschinen=await scope.machine_ids()
    )


@router.get(
    "/explanations/{explanation_id}/siblings",
    response_model=list[SiblingReference],
)
async def get_explanation_siblings(
    explanation_id: int, session: SessionDep, scope: ResourceScopeDep
) -> list[SiblingReference]:
    """Liefert die EINGEFRORENEN Schwester-Referenzen einer gespeicherten Erklärung
    (ehrlich aus realen Recall-Treffern, §21-D). Keine → leere Liste (kein Fake).
    404, wenn die Erklärung fehlt oder außerhalb des Maschinen-Ausschnitts liegt.

    Die Referenzen zeigen auf ANDERE Maschinen — das ist ihr Zweck, denn der
    Gedächtnis-Abruf sucht nach Maschinenklasse und Signatur, nicht nach Maschine.
    Sie tragen deshalb eine eigene Maschinen-Kennung und erben den Ausschnitt ihrer
    Erklärung NICHT. Gefiltert wird zweimal: beim Erzeugen gegen den Ausschnitt des
    Auslösers, hier gegen den des Lesers — ein Schnappschuss, den ein Manager erzeugt
    hat, darf einem Werker nicht mehr zeigen, als ihm zusteht."""
    record = await _sichtbare_erklaerung(session, scope, explanation_id)
    return nur_sichtbare_geschwister(
        [SiblingReference.model_validate(item) for item in (record.siblings_snapshot or [])],
        await scope.machine_ids(),
    )
