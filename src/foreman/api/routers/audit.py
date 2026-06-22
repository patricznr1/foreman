# ============================================================
#  FOREMAN — api/routers/audit.py (Sektion I)
#  Zweck: Read-API des Audit-Trails — GET /api/v1/audit, gefiltert + paginiert,
#         jüngste zuerst. Nur Manager/Admin (Studie-Rollenmatrix); Schichtleiter/
#         Techniker/Werker erhalten 403. `actor` bleibt pseudonym.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from foreman.api.deps import CurrentUser, SessionDep
from foreman.audit.schemas import AuditEntryRead
from foreman.audit.service import list_audit
from foreman.db.models import AuditLog
from foreman.realtime.authz import ROLE_MANAGER

router = APIRouter(prefix="/audit", tags=["audit"])

# Audit-Einsicht: Manager/Admin (es gibt keine separate „admin"-Rolle → Manager).
# Schichtleiter/Techniker/Werker bewusst ausgeschlossen (Plattform-/Audit-Kontext).
_AUDIT_ROLES = frozenset({ROLE_MANAGER})


@router.get("", response_model=list[AuditEntryRead])
async def list_audit_entries(
    session: SessionDep,
    user: CurrentUser,
    action_type: str | None = Query(default=None),
    target_kind: str | None = Query(default=None),
    target_id: int | None = Query(default=None),
    actor: str | None = Query(default=None),
    machine_id: int | None = Query(default=None),
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[AuditLog]:
    """Audit-Trail (jüngste zuerst), gefiltert. Nur Manager/Admin — sonst 403."""
    if user.role not in _AUDIT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Kein Zugriff auf den Audit-Trail"
        )
    return await list_audit(
        session,
        action_type=action_type,
        target_kind=target_kind,
        target_id=target_id,
        actor=actor,
        machine_id=machine_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
