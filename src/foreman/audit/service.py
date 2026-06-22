# ============================================================
#  FOREMAN — audit/service.py (Sektion I)
#  Zweck: Lese-Kern des Audit-Trails — eine gefilterte, paginierte Abfrage,
#         jüngste zuerst. Reine Query-Schicht (keine Rollen-Logik; die sitzt im
#         Router). `actor` bleibt pseudonym (HMAC-Token), nie aufgelöst.
#  Architektur-Einordnung: Audit-Schicht (Schicht 2).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import AuditLog


async def list_audit(
    session: AsyncSession,
    *,
    action_type: str | None = None,
    target_kind: str | None = None,
    target_id: int | None = None,
    actor: str | None = None,
    machine_id: int | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[AuditLog]:
    """Listet Audit-Zeilen (jüngste zuerst), optional gefiltert. Pseudonym."""
    stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
    if action_type is not None:
        stmt = stmt.where(AuditLog.action_type == action_type)
    if target_kind is not None:
        stmt = stmt.where(AuditLog.target_kind == target_kind)
    if target_id is not None:
        stmt = stmt.where(AuditLog.target_id == target_id)
    if actor is not None:
        stmt = stmt.where(AuditLog.actor == actor)
    if machine_id is not None:
        stmt = stmt.where(AuditLog.machine_id == machine_id)
    if since is not None:
        stmt = stmt.where(AuditLog.occurred_at >= since)
    if until is not None:
        stmt = stmt.where(AuditLog.occurred_at <= until)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()
