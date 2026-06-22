# ============================================================
#  FOREMAN — audit/schemas.py (Sektion I)
#  Zweck: Pydantic-Verträge des Audit-Trails — `AuditEntry` als interner
#         Schreib-Eingang (Writer) und `AuditEntryRead` als pseudonyme
#         Lese-Ausgabe der Read-API. `actor` ist stets ein HMAC-Token (§8).
#  Architektur-Einordnung: Audit-Schicht (Schicht 2).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEntry(BaseModel):
    """Interner, unveränderlicher Schreib-Eingang für eine Audit-Zeile.

    Wird vom Writer aus den realen Quellen (HITL-Quittierung, MCP-Abruf) gebaut.
    `actor` ist bereits pseudonymisiert (HMAC-Token), nie Klartext.
    """

    model_config = ConfigDict(frozen=True)

    action_type: str
    origin: str
    actor: str | None = None
    actor_role: str | None = None
    target_kind: str | None = None
    target_id: int | None = None
    machine_id: int | None = None
    detail: dict[str, Any] | None = None
    occurred_at: datetime | None = None


class AuditEntryRead(BaseModel):
    """Pseudonyme Lese-Sicht einer Audit-Zeile (Read-API, nur Manager).

    Bewusst OHNE die Legacy-Spalten `action`/`target` und OHNE `user_id` — der
    typisierte, pseudonyme Trail ist die maßgebliche Außensicht.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    occurred_at: datetime | None
    created_at: datetime
    action_type: str | None
    actor: str | None  # HMAC-Token, nie Klartext
    actor_role: str | None
    origin: str | None
    target_kind: str | None
    target_id: int | None
    machine_id: int | None
    detail: dict[str, Any] | None
