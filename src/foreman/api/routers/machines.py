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

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import CurrentUser, ResourceScopeDep, SessionDep
from foreman.db.models import Machine
from foreman.schemas.resources import MachineCreate, MachineRead

router = APIRouter(prefix="/machines", tags=["machines"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MachineRead)
async def create_machine(body: MachineCreate, session: SessionDep, user: CurrentUser) -> Machine:
    """Legt eine Maschine an — Identitätsprüfung, kein Ressourcen-Ausschnitt.

    Der Ausschnitt ist hier bewusst NICHT das Mittel, und der Grund ist strukturell:
    Er leitet sich aus den zugewiesenen Maschinen ab. Eine frisch angelegte Linie
    enthält noch keine, liegt also außerhalb des Ausschnitts ihres eigenen Erzeugers
    — eine Scope-Prüfung an dieser Stelle verböte, die erste Maschine einer Linie
    anzulegen. Welche Rollen Stammdaten anlegen dürfen, gehört deshalb in die
    Rollenmatrix (`require_roles`), nicht an den Ausschnitt.
    """
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
