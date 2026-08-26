# ============================================================
#  FOREMAN — api/routers/machines.py
#  Zweck: CRUD für Maschinen (/api/v1/machines), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). machines.external_id ist
#         eine anonymisierte Maschinen-Kennung (kein Personenbezug).
#  Maschinen-Scope (§20.4): Hier ist die Maschine nicht der Bezug, sondern die
#         Ressource selbst — die Liste zeigt den Ausschnitt, der Einzelabruf
#         antwortet außerhalb davon mit 403. Bewusst 403 und nicht 404: Die
#         Maschinen-Kennung ist ein Stammdatum, das der Anfragende aus seiner
#         eigenen Liste kennt; zu verschweigen gäbe es nichts.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import ResourceScopeDep, SessionDep, require_roles
from foreman.db.models import Machine, User
from foreman.realtime.authz import ROLE_MANAGER
from foreman.schemas.resources import MachineCreate, MachineRead

router = APIRouter(prefix="/machines", tags=["machines"])

# Anlagenstruktur pflegt der Betreiber: Manager (es gibt keine separate
# „admin"-Rolle → Manager, wie beim Audit-Trail in api/routers/audit.py).
# ANSCHLUSSPUNKT: Sobald eine eigene Administrations-Rolle entsteht, wandert die
# Berechtigung dorthin — hier ist es dann eine Zeile.
# Warum die Rolle und NICHT der Maschinen-Ausschnitt: Der Ausschnitt leitet sich
# aus zugewiesenen Maschinen ab, und eine frisch angelegte Linie enthält noch
# keine. Eine Scope-Prüfung verböte, die erste Maschine einer Linie anzulegen.
StammdatenVerwalter = Annotated[User, Depends(require_roles(ROLE_MANAGER))]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MachineRead)
async def create_machine(
    body: MachineCreate, session: SessionDep, user: StammdatenVerwalter
) -> Machine:
    """Legt eine Maschine an — Betreiber-Handlung, siehe StammdatenVerwalter."""
    obj = Machine(**body.model_dump())
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[MachineRead])
async def list_machines(
    session: SessionDep,
    scope: ResourceScopeDep,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[Machine]:
    """Die Maschinen im Ausschnitt des Anfragenden."""
    stmt = await scope.limit_to(select(Machine).order_by(Machine.id), Machine.id)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{machine_id}", response_model=MachineRead)
async def get_machine(machine_id: int, session: SessionDep, scope: ResourceScopeDep) -> Machine:
    """Eine Maschine — 403 außerhalb des Ausschnitts, 404 wenn unbekannt."""
    await scope.require(machine_id)
    obj = await session.get(Machine, machine_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maschine nicht gefunden")
    return obj
