# ============================================================
#  FOREMAN — api/routers/maintenance_events.py
#  Zweck: CRUD für Wartungsereignisse (/api/v1/maintenance_events), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2).
#  Datenschutz (§8): `performed_by` wird im Schreibpfad zu einem HMAC-Token
#         über die user_id tokenisiert — nie Klartext.
#  Identitätsbindung (§19): `performed_by` ist ein Nachweis-Feld (§8, auditiert
#         re-identifizierbar). Default ist die Token-Identität; ein abweichender
#         Wert ist der Nachtrag für eine dritte Person und den aufsichtsführenden
#         Rollen vorbehalten.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import CurrentUser, PseudonymizerDep, SessionDep
from foreman.core.roles import Role
from foreman.db.models import MaintenanceEvent
from foreman.schemas.resources import MaintenanceEventCreate, MaintenanceEventRead

router = APIRouter(prefix="/maintenance_events", tags=["maintenance_events"])

# Rollen, die einen Wartungsnachweis für eine dritte Person eintragen dürfen
# (Rollenmatrix 3.1). Ein `worker` trägt ausschließlich für sich selbst ein.
_DELEGATING_ROLES = frozenset({Role.SHIFT_LEAD, Role.TECHNICIAN, Role.MANAGER})


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MaintenanceEventRead)
async def create_maintenance_event(
    body: MaintenanceEventCreate,
    current_user: CurrentUser,
    session: SessionDep,
    pseudo: PseudonymizerDep,
) -> MaintenanceEvent:
    data = body.model_dump()
    if data.get("performed_at") is None:
        data.pop("performed_at", None)  # Server-Default greift
    own_id = str(current_user.id)
    # Leer/weggelassen → der eingeloggte Nutzer. Nur ein ABWEICHENDER Wert ist ein
    # Nachtrag für eine dritte Person und damit rollenbeschränkt.
    performed_by = data.pop("performed_by", None) or own_id
    if performed_by != own_id and current_user.role not in _DELEGATING_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Deine Rolle darf Wartungen nur für die eigene Person eintragen",
        )
    obj = MaintenanceEvent(
        **data,
        performed_by=pseudo.tokenize_worker(performed_by),
    )
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[MaintenanceEventRead])
async def list_maintenance_events(
    session: SessionDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[MaintenanceEvent]:
    stmt = select(MaintenanceEvent).order_by(MaintenanceEvent.id)
    if machine_id is not None:
        stmt = stmt.where(MaintenanceEvent.machine_id == machine_id)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{event_id}", response_model=MaintenanceEventRead)
async def get_maintenance_event(event_id: int, session: SessionDep) -> MaintenanceEvent:
    obj = await session.get(MaintenanceEvent, event_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wartungsereignis nicht gefunden"
        )
    return obj
