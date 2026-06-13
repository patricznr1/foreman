# ============================================================
#  FOREMAN — api/routers/lines.py
#  Zweck: CRUD für Fertigungsstraßen (/api/v1/lines), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Wurzel der Hierarchie
#         Linie → Maschine → Komponente → Datenpunkt.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import SessionDep
from foreman.db.models import Line
from foreman.schemas.resources import LineCreate, LineRead

router = APIRouter(prefix="/lines", tags=["lines"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=LineRead)
async def create_line(body: LineCreate, session: SessionDep) -> Line:
    obj = Line(**body.model_dump())
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[LineRead])
async def list_lines(
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[Line]:
    result = await session.scalars(
        select(Line).order_by(Line.id).limit(limit).offset(offset)
    )
    return result.all()


@router.get("/{line_id}", response_model=LineRead)
async def get_line(line_id: int, session: SessionDep) -> Line:
    obj = await session.get(Line, line_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linie nicht gefunden")
    return obj
