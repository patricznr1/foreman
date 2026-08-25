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

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import CurrentUser, ResourceScopeDep, SessionDep
from foreman.db.models import Line
from foreman.schemas.resources import LineCreate, LineRead

router = APIRouter(prefix="/lines", tags=["lines"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=LineRead)
async def create_line(body: LineCreate, session: SessionDep, user: CurrentUser) -> Line:
    """Legt eine Fertigungsstraße an.

    Eine neue Linie hat noch keine Zugehörigkeit, an der ein Ausschnitt hinge —
    hier greift die Identitätsprüfung. Welche Rollen Stammdaten anlegen dürfen,
    ist eine fachliche Festlegung der Rollenmatrix.
    """
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
