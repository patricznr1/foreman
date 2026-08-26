# ============================================================
#  FOREMAN — api/routers/components.py
#  Zweck: CRUD für Komponenten (/api/v1/components), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Komponente hängt an Maschine.
#  Maschinen-Scope (§20.4): jede Route führt `ResourceScopeDep` — die Komponente
#         folgt der Sichtbarkeit ihrer Maschine.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import ResourceScopeDep, SessionDep, require_roles
from foreman.db.models import Component, User
from foreman.realtime.authz import ROLE_MANAGER
from foreman.schemas.resources import ComponentCreate, ComponentRead

router = APIRouter(prefix="/components", tags=["components"])

# Anlagenstruktur pflegt der Betreiber: Manager (es gibt keine separate
# „admin"-Rolle → Manager, wie beim Audit-Trail in api/routers/audit.py).
# ANSCHLUSSPUNKT: Sobald eine eigene Administrations-Rolle entsteht, wandert die
# Berechtigung dorthin — hier ist es dann eine Zeile.
StammdatenVerwalter = Annotated[User, Depends(require_roles(ROLE_MANAGER))]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ComponentRead)
async def create_component(
    body: ComponentCreate,
    session: SessionDep,
    scope: ResourceScopeDep,
    user: StammdatenVerwalter,
) -> Component:
    """Legt eine Komponente an — Betreiber-Handlung, siehe StammdatenVerwalter.

    Die Ausschnitts-Prüfung bleibt stehen, obwohl sie für `manager` heute nichts
    bewirkt (unbeschränkte Rolle). Sie trägt in dem Moment wieder, in dem die
    Verwaltungsrolle um eine beschränkte erweitert wird — sie jetzt zu entfernen
    hieße, sie später neu zu finden.
    """
    await scope.require(body.machine_id)
    obj = Component(**body.model_dump())
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[ComponentRead])
async def list_components(
    session: SessionDep,
    scope: ResourceScopeDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[Component]:
    """Komponenten im Maschinen-Ausschnitt des Anfragenden."""
    stmt = await scope.limit_to(
        select(Component).order_by(Component.id), Component.machine_id, machine_id=machine_id
    )
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{component_id}", response_model=ComponentRead)
async def get_component(
    component_id: int, session: SessionDep, scope: ResourceScopeDep
) -> Component:
    """Eine Komponente — 404 auch für eine Maschine außerhalb des Ausschnitts."""
    obj = await session.get(Component, component_id)
    if obj is None or not await scope.can_see(obj.machine_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Komponente nicht gefunden"
        )
    return obj
