# ============================================================
#  FOREMAN — api/routers/alarms.py
#  Zweck: CRUD für Alarme/Nothalt (/api/v1/alarms), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Nothalt = category=safety,
#         severity=emergency. Die Quittierungs-Felder tragen die HITL-Semantik;
#         der Quittierungs-Flow selbst kommt in F4 (hier nur Schema + Schreibpfad).
#  Datenschutz (§8): `acknowledged_by` wird zu einem HMAC-Token über die user_id
#         tokenisiert — nie Klartext.
#  Maschinen-Scope (§20.4): jede Route führt `ResourceScopeDep` — ein Alarm gehört
#         zu genau einer Maschine und folgt deren Sichtbarkeit.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import PseudonymizerDep, ResourceScopeDep, SessionDep
from foreman.db.models import Alarm
from foreman.schemas.resources import AlarmCreate, AlarmRead

router = APIRouter(prefix="/alarms", tags=["alarms"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AlarmRead)
async def create_alarm(
    body: AlarmCreate, session: SessionDep, pseudo: PseudonymizerDep, scope: ResourceScopeDep
) -> Alarm:
    await scope.require(body.machine_id)
    data = body.model_dump()
    if data.get("raised_at") is None:
        data.pop("raised_at", None)  # Server-Default greift
    acknowledged_by = data.pop("acknowledged_by", None)
    obj = Alarm(
        **data,
        acknowledged_by=(pseudo.tokenize_worker(acknowledged_by) if acknowledged_by else None),
    )
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[AlarmRead])
async def list_alarms(
    session: SessionDep,
    scope: ResourceScopeDep,
    machine_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[Alarm]:
    """Alarme im Maschinen-Ausschnitt des Anfragenden (jüngste zuerst)."""
    stmt = await scope.limit_to(
        select(Alarm).order_by(Alarm.raised_at.desc()), Alarm.machine_id, machine_id=machine_id
    )
    if category is not None:
        stmt = stmt.where(Alarm.category == category)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{alarm_id}", response_model=AlarmRead)
async def get_alarm(alarm_id: int, session: SessionDep, scope: ResourceScopeDep) -> Alarm:
    """Ein Alarm — 404 auch für eine Maschine außerhalb des Ausschnitts."""
    obj = await session.get(Alarm, alarm_id)
    if obj is None or not await scope.can_see(obj.machine_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alarm nicht gefunden")
    return obj
