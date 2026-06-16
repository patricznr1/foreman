# ============================================================
#  FOREMAN — realtime/notify.py
#  Zweck: Producer-Primitive des Live-Push-Layers (F5). Setzt GENAU EIN pg_notify
#         pro Aufruf ab — gedacht für genau einen Aufruf pro Commit/Batch, nicht
#         pro Zeile (Vorgabe 4). Das NOTIFY läuft über die übergebene Session und
#         wird daher transaktional erst beim Commit dieser Session zugestellt.
#  Architektur-Einordnung: Live-Push-Layer (F5), Producer-Seite. Hängt nur an der
#         Session + am NOTIFY-Vertrag (channels) — KEINE Abhängigkeit auf Hub/WS.
#         Dadurch darf der Schreibpfad (ingestion, readings-Route) sie aufrufen.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.realtime.channels import DASHBOARD_CHANNEL, ChangeSet, encode_change


async def notify_changes(session: AsyncSession, change: ChangeSet) -> bool:
    """Setzt ein einzelnes pg_notify für das ChangeSet ab (transaktional).

    No-op bei leerem ChangeSet. Gibt zurück, ob ein NOTIFY abgesetzt wurde — der
    Aufrufer ruft genau einmal pro Commit/Batch auf, sodass der Hub serverseitig
    pro Thema debouncen und dann konsolidiert über den Read-Core nachladen kann.
    """
    if change.is_empty():
        return False
    await session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": DASHBOARD_CHANNEL, "payload": encode_change(change)},
    )
    return True
