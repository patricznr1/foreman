# ============================================================
#  FOREMAN — api/routers/data_points.py
#  Zweck: CRUD für Datenpunkte/Tags (/api/v1/data_points), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Datenpunkt hängt immer an
#         einer Maschine, optional an einer Komponente.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import SessionDep
from foreman.db.models import DataPoint
from foreman.schemas.resources import DataPointCreate, DataPointRead

router = APIRouter(prefix="/data_points", tags=["data_points"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DataPointRead)
async def create_data_point(body: DataPointCreate, session: SessionDep) -> DataPoint:
    obj = DataPoint(**body.model_dump())
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[DataPointRead])
async def list_data_points(
    session: SessionDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[DataPoint]:
    stmt = select(DataPoint).order_by(DataPoint.id)
    if machine_id is not None:
        stmt = stmt.where(DataPoint.machine_id == machine_id)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{data_point_id}", response_model=DataPointRead)
async def get_data_point(data_point_id: int, session: SessionDep) -> DataPoint:
    obj = await session.get(DataPoint, data_point_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Datenpunkt nicht gefunden"
        )
    return obj
