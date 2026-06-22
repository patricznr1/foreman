# ============================================================
#  FOREMAN — reasoners/drift/router.py
#  Zweck: HTTP-Routen des Drift-Reasoners (GROUND_TRUTH §4, F4 Baustein 8) unter
#         /api/v1/reasoners/drift/: Auflistung der Drift-Warnungen (Ergebnisse)
#         + HITL-Quittierungs-Endpunkt.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Human-in-the-Loop (§8/§11.2):
#         eine drift-abgeleitete Warnung gilt erst nach Operator-Quittierung
#         (acknowledged_at/acknowledged_by) als erledigt. `acknowledged_by` wird
#         über tokenize_worker (HMAC, §8) tokenisiert — Nachweis-Bezug, nie
#         Klartext. KEINE Aktorik: der Endpunkt schreibt nur den Quittierungs-
#         Status, schaltet nichts.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import CurrentUser, PseudonymizerDep, SessionDep
from foreman.audit.writer import hitl_acknowledge_entry, record
from foreman.db.models import Alarm
from foreman.reasoners.drift.service import DRIFT_ALARM_CODE
from foreman.schemas.resources import AlarmRead

router = APIRouter(prefix="/reasoners/drift", tags=["drift"])


@router.get("/alarms", response_model=list[AlarmRead])
async def list_drift_alarms(
    session: SessionDep,
    machine_id: int | None = Query(default=None),
    acknowledged: bool | None = Query(
        default=None, description="Nur (un)quittierte Warnungen; None = alle."
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[Alarm]:
    """Listet die vom Drift-Reasoner erzeugten Warnungen (code=DRIFT)."""
    stmt = select(Alarm).where(Alarm.code == DRIFT_ALARM_CODE).order_by(Alarm.raised_at.desc())
    if machine_id is not None:
        stmt = stmt.where(Alarm.machine_id == machine_id)
    if acknowledged is True:
        stmt = stmt.where(Alarm.acknowledged_at.is_not(None))
    elif acknowledged is False:
        stmt = stmt.where(Alarm.acknowledged_at.is_(None))
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.post("/alarms/{alarm_id}/acknowledge", response_model=AlarmRead)
async def acknowledge_drift_alarm(
    alarm_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    pseudo: PseudonymizerDep,
) -> Alarm:
    """Quittiert eine Drift-Warnung (HITL). Erst danach gilt sie als erledigt.

    Erfordert einen authentifizierten Operator; `acknowledged_by` wird als
    HMAC-Token über die user_id abgelegt (Nachweis-Bezug, §8). Keine Aktorik.
    """
    alarm = await session.get(Alarm, alarm_id)
    if alarm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Drift-Warnung nicht gefunden"
        )
    if alarm.code != DRIFT_ALARM_CODE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alarm ist keine Drift-Warnung des Reasoners",
        )
    alarm.acknowledged_at = datetime.now(UTC)
    alarm.acknowledged_by = pseudo.tokenize_worker(str(current_user.id))
    await session.flush()
    # Audit-Trail (Sektion I): die HITL-Entscheidung als pseudonyme Zeile IN derselben
    # Transaktion festhalten — atomar mit der Quittierung, kein eigener Commit. Keine
    # Aktorik; der Audit protokolliert die Entscheidung, löst keine aus.
    await record(
        session,
        hitl_acknowledge_entry(
            pseudo=pseudo,
            user_id=str(current_user.id),
            actor_role=current_user.role,
            alarm_id=alarm.id,
            machine_id=alarm.machine_id,
            alarm_code=alarm.code,
            severity=alarm.severity,
        ),
    )
    await session.refresh(alarm)
    return alarm
