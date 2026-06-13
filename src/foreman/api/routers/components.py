# ============================================================
#  FOREMAN — api/routers/components.py
#  Zweck: CRUD für Komponenten (/api/v1/components), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Komponente hängt an Maschine.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import SessionDep
from foreman.db.models import Component
from foreman.schemas.resources import ComponentCreate, ComponentRead

router = APIRouter(prefix="/components", tags=["components"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ComponentRead)
async def create_component(body: ComponentCreate, session: SessionDep) -> Component:
    obj = Component(**body.model_dump())
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[ComponentRead])
async def list_components(
    session: SessionDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[Component]:
    stmt = select(Component).order_by(Component.id)
    if machine_id is not None:
        stmt = stmt.where(Component.machine_id == machine_id)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{component_id}", response_model=ComponentRead)
async def get_component(component_id: int, session: SessionDep) -> Component:
    obj = await session.get(Component, component_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Komponente nicht gefunden"
        )
    return obj
