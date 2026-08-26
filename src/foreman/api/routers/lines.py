# ============================================================
#  FOREMAN — api/routers/lines.py
#  Zweck: CRUD für Fertigungsstraßen (/api/v1/lines), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Wurzel der Hierarchie
#         Linie → Maschine → Komponente → Datenpunkt.
#  Linien-Scope (§20.4): Die Lese-Routen führen `ResourceScopeDep` und zeigen die
#         Linien, die der Anfragende sehen darf — für einen Werker sind das die
#         Linien seiner Maschinen, abgeleitet statt getrennt gepflegt.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import ResourceScopeDep, SessionDep, require_roles
from foreman.db.models import Line, User
from foreman.realtime.authz import ROLE_MANAGER
from foreman.schemas.resources import LineCreate, LineRead

router = APIRouter(prefix="/lines", tags=["lines"])

# Anlagenstruktur pflegt der Betreiber: Manager (es gibt keine separate
# „admin"-Rolle → Manager, wie beim Audit-Trail in api/routers/audit.py).
# ANSCHLUSSPUNKT: Sobald eine eigene Administrations-Rolle entsteht, wandert die
# Berechtigung dorthin — hier ist es dann eine Zeile.
# Warum die Rolle und NICHT der Maschinen-Ausschnitt: Der Ausschnitt leitet sich
# aus zugewiesenen Maschinen ab, und eine frisch angelegte Linie enthält noch
# keine. Eine Scope-Prüfung verböte, die erste Maschine einer Linie anzulegen.
StammdatenVerwalter = Annotated[User, Depends(require_roles(ROLE_MANAGER))]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=LineRead)
async def create_line(body: LineCreate, session: SessionDep, user: StammdatenVerwalter) -> Line:
    """Legt eine Fertigungsstraße an — Betreiber-Handlung, siehe StammdatenVerwalter."""
    obj = Line(**body.model_dump())
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[LineRead])
async def list_lines(
    session: SessionDep,
    scope: ResourceScopeDep,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[Line]:
    """Die Linien im Ausschnitt des Anfragenden."""
    stmt = await scope.limit_to_lines(select(Line).order_by(Line.id), Line.id)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{line_id}", response_model=LineRead)
async def get_line(line_id: int, session: SessionDep, scope: ResourceScopeDep) -> Line:
    """Eine Linie — 403 außerhalb des Ausschnitts, 404 wenn unbekannt."""
    await scope.require_line(line_id)
    obj = await session.get(Line, line_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linie nicht gefunden")
    return obj
