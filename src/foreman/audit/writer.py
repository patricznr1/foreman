# ============================================================
#  FOREMAN — audit/writer.py (Sektion I)
#  Zweck: Schreibpfade des Audit-Trails. Zwei Wege, eine Zeilen-Konstruktion:
#         (1) `record` — in-session/atomar (HITL-Quittierung, gemeinsame TX mit
#             dem Geschäfts-Write); (2) `emit_mcp_retrieval` — best-effort auf
#             EIGENER Session/Commit (MCP-Abruf), strikt getrennt vom read-only-
#             Tool-Pfad, damit die MCP-Read-Invariante (I) unangetastet bleibt.
#  Architektur-Einordnung: Audit-Schicht (Schicht 2).
#  Datenschutz (§8): `actor` ist immer ein HMAC-Token (Werker-ID bzw. konstantes
#         MCP-Consumer-Label) — nie Klartext. `detail` ist PII-frei (IDs/Token).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from foreman.audit.schemas import AuditEntry
from foreman.config import get_settings
from foreman.core.pseudonymize import Pseudonymizer, build_pseudonymizer
from foreman.db.models import AuditLog
from foreman.db.session import get_sessionmaker

logger = logging.getLogger(__name__)

# --- Vokabular (deckungsgleich mit den DB-CHECK-Constraints in models.py/0010) ---
ACTION_HITL_ACKNOWLEDGE = "hitl_acknowledge"
ACTION_MCP_RETRIEVAL = "mcp_retrieval"
ORIGIN_DASHBOARD = "dashboard"
ORIGIN_MCP = "mcp"
ORIGIN_SYSTEM = "system"

# Single-Consumer-Label: mcp/auth.py kennt nur EINEN geteilten Token, keine
# Per-Client-Identität. Der MCP-Akteur ist daher ein konstantes, pseudonymisiertes
# Consumer-Label — ehrlich genau eine Konsumenten-Grenze. Per-Client-Attribution
# ist [VISION] bis es echte Per-Client-Credentials gibt.
MCP_CONSUMER_LABEL = "mcp-shared-consumer"
MCP_ACTOR_ROLE = "mcp_client"


def build_audit_log(entry: AuditEntry) -> AuditLog:
    """Bildet eine `AuditLog`-Zeile aus einem `AuditEntry` (rein, testbar).

    Spiegelt den `action_type` in die Legacy-NOT-NULL-Spalte `action` und baut
    aus Ziel-Art + ID einen menschenlesbaren Legacy-`target`. `user_id` bleibt
    bewusst leer (§8). `occurred_at` wird nur gesetzt, wenn vorhanden — sonst
    greift der DB-server_default (now()).
    """
    legacy_target: str | None = entry.target_kind
    if entry.target_kind is not None and entry.target_id is not None:
        legacy_target = f"{entry.target_kind}:{entry.target_id}"
    row = AuditLog(
        action=entry.action_type,  # Legacy-NOT-NULL gespiegelt
        target=legacy_target,
        action_type=entry.action_type,
        actor=entry.actor,
        actor_role=entry.actor_role,
        origin=entry.origin,
        target_kind=entry.target_kind,
        target_id=entry.target_id,
        machine_id=entry.machine_id,
        detail=entry.detail,
    )
    if entry.occurred_at is not None:
        row.occurred_at = entry.occurred_at
    return row


def hitl_acknowledge_entry(
    *,
    pseudo: Pseudonymizer,
    user_id: str,
    actor_role: str,
    alarm_id: int,
    machine_id: int,
    alarm_code: str | None,
    severity: str,
) -> AuditEntry:
    """Baut den Audit-Eintrag einer HITL-Alarm-Quittierung (origin=dashboard).

    `actor` = HMAC-Token über die user_id — identisch zu `alarms.acknowledged_by` (§8).
    """
    return AuditEntry(
        action_type=ACTION_HITL_ACKNOWLEDGE,
        origin=ORIGIN_DASHBOARD,
        actor=pseudo.tokenize_worker(user_id),
        actor_role=actor_role,
        target_kind="alarm",
        target_id=alarm_id,
        machine_id=machine_id,
        detail={"decision": "acknowledge", "alarm_code": alarm_code, "severity": severity},
    )


def mcp_retrieval_entry(
    *,
    pseudo: Pseudonymizer,
    tool: str,
    target_kind: str | None,
    target_id: int | None,
    machine_id: int | None,
    success: bool,
) -> AuditEntry:
    """Baut den Audit-Eintrag eines MCP-Abrufs (origin=mcp).

    `actor` = pseudonymisiertes Single-Consumer-Label (kein Klartext). `detail`
    trägt das Tool + das Ergebnis (ok/error) — keine Freitext-Payload (PII-frei).
    """
    return AuditEntry(
        action_type=ACTION_MCP_RETRIEVAL,
        origin=ORIGIN_MCP,
        actor=pseudo.tokenize_worker(MCP_CONSUMER_LABEL),
        actor_role=MCP_ACTOR_ROLE,
        target_kind=target_kind,
        target_id=target_id,
        machine_id=machine_id,
        detail={"tool": tool, "result": "ok" if success else "error"},
    )


async def record(session: AsyncSession, entry: AuditEntry) -> AuditLog:
    """Schreibt einen Audit-Eintrag IN die übergebene Session (atomar, kein Commit).

    Für den HITL-Pfad: der Audit-Eintrag teilt die Transaktion des Geschäfts-Writes
    (Quittierung) — beide gelingen oder scheitern gemeinsam. Der Commit gehört der
    aufrufenden Session-Dependency.
    """
    row = build_audit_log(entry)
    session.add(row)
    await session.flush()
    return row


async def emit_mcp_retrieval(
    *,
    tool: str,
    target_kind: str | None,
    target_id: int | None,
    machine_id: int | None,
    success: bool,
    pseudonymizer: Pseudonymizer | None = None,
) -> None:
    """Schreibt einen MCP-Abruf-Eintrag auf EIGENER Session + Commit (best-effort).

    Strikt getrennt vom read-only-Tool-Pfad: läuft NACH dem Schließen der
    Read-only-Session, öffnet eine eigene Session und committet selbst — die
    MCP-Read-Invariante (I) bleibt unberührt. Schluckt jeden Fehler (loggt nur),
    damit ein Audit-Ausfall den Abruf nie bricht.
    """
    try:
        pseudo = pseudonymizer or build_pseudonymizer(get_settings())
        entry = mcp_retrieval_entry(
            pseudo=pseudo,
            tool=tool,
            target_kind=target_kind,
            target_id=target_id,
            machine_id=machine_id,
            success=success,
        )
        maker = get_sessionmaker()
        async with maker() as session:
            session.add(build_audit_log(entry))
            await session.commit()
    except Exception as exc:  # best-effort: Audit darf den Read-Pfad nie brechen.
        logger.warning("❌ MCP-Audit-Write fehlgeschlagen (tool=%s): %s", tool, exc)
