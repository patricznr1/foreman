# ============================================================
#  FOREMAN — api/routers/data_points.py
#  Zweck: CRUD für Datenpunkte/Tags (/api/v1/data_points), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Datenpunkt hängt immer an
#         einer Maschine, optional an einer Komponente.
#  Maschinen-Scope (§20.4): jede Route führt `ResourceScopeDep` — der Datenpunkt
#         folgt der Sichtbarkeit seiner Maschine.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import ResourceScopeDep, SessionDep, require_roles
from foreman.db.models import DataPoint, User
from foreman.realtime.authz import ROLE_MANAGER
from foreman.schemas.resources import DataPointCreate, DataPointRead

router = APIRouter(prefix="/data_points", tags=["data_points"])

# Anlagenstruktur pflegt der Betreiber: Manager (es gibt keine separate
# „admin"-Rolle → Manager, wie beim Audit-Trail in api/routers/audit.py).
# ANSCHLUSSPUNKT: Sobald eine eigene Administrations-Rolle entsteht, wandert die
# Berechtigung dorthin — hier ist es dann eine Zeile.
StammdatenVerwalter = Annotated[User, Depends(require_roles(ROLE_MANAGER))]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DataPointRead)
async def create_data_point(
    body: DataPointCreate,
    session: SessionDep,
    scope: ResourceScopeDep,
    user: StammdatenVerwalter,
) -> DataPoint:
    """Legt einen Datenpunkt an — Betreiber-Handlung, siehe StammdatenVerwalter.

    Zur bleibenden Ausschnitts-Prüfung siehe die Begründung in `components.py`.
    """
    await scope.require(body.machine_id)
    obj = DataPoint(**body.model_dump())
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[DataPointRead])
async def list_data_points(
    session: SessionDep,
    scope: ResourceScopeDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[DataPoint]:
    """Datenpunkte im Maschinen-Ausschnitt des Anfragenden."""
    stmt = await scope.limit_to(
        select(DataPoint).order_by(DataPoint.id), DataPoint.machine_id, machine_id=machine_id
    )
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{data_point_id}", response_model=DataPointRead)
async def get_data_point(
    data_point_id: int, session: SessionDep, scope: ResourceScopeDep
) -> DataPoint:
    """Ein Datenpunkt — 404 auch für eine Maschine außerhalb des Ausschnitts."""
    obj = await session.get(DataPoint, data_point_id)
    if obj is None or not await scope.can_see(obj.machine_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Datenpunkt nicht gefunden"
        )
    return obj
