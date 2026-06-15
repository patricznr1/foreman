# ============================================================
#  FOREMAN — api/routers/machines.py
#  Zweck: CRUD für Maschinen (/api/v1/machines), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). machines.external_id ist
#         eine anonymisierte Maschinen-Kennung (kein Personenbezug).
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import SessionDep
from foreman.db.models import Machine
from foreman.schemas.resources import MachineCreate, MachineRead

router = APIRouter(prefix="/machines", tags=["machines"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MachineRead)
async def create_machine(body: MachineCreate, session: SessionDep) -> Machine:
    obj = Machine(**body.model_dump())
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[MachineRead])
async def list_machines(
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[Machine]:
    result = await session.scalars(select(Machine).order_by(Machine.id).limit(limit).offset(offset))
    return result.all()


@router.get("/{machine_id}", response_model=MachineRead)
async def get_machine(machine_id: int, session: SessionDep) -> Machine:
    obj = await session.get(Machine, machine_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maschine nicht gefunden")
    return obj
