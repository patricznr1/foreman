# ============================================================
#  FOREMAN — api/routers/production_runs.py
#  Zweck: CRUD für Produktionskontext (/api/v1/production_runs), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Produktionskontext liegt
#         auf Linien-Ebene (Welt A).
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import SessionDep
from foreman.db.models import ProductionRun
from foreman.schemas.resources import ProductionRunCreate, ProductionRunRead

router = APIRouter(prefix="/production_runs", tags=["production_runs"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProductionRunRead)
async def create_production_run(body: ProductionRunCreate, session: SessionDep) -> ProductionRun:
    data = body.model_dump()
    # started_at hat einen Server-Default — bei None weglassen, damit der greift.
    if data.get("started_at") is None:
        data.pop("started_at", None)
    obj = ProductionRun(**data)
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[ProductionRunRead])
async def list_production_runs(
    session: SessionDep,
    line_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[ProductionRun]:
    stmt = select(ProductionRun).order_by(ProductionRun.id)
    if line_id is not None:
        stmt = stmt.where(ProductionRun.line_id == line_id)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{run_id}", response_model=ProductionRunRead)
async def get_production_run(run_id: int, session: SessionDep) -> ProductionRun:
    obj = await session.get(ProductionRun, run_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Produktionslauf nicht gefunden"
        )
    return obj
