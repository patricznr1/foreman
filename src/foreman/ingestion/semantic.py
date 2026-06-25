# ============================================================
#  FOREMAN — ingestion/semantic.py
#  Zweck: Best-effort Dual-Write diskreter semantischer Ereignisse ans
#         Gedächtnis-Substrat + Spiegel-Zeile in `semantic_events` (F3).
#  Architektur-Einordnung: Ingestion (Schicht 2). Realisiert den §9-Fallback:
#         Die semantic_events-Zeile wird IMMER geschrieben; der remember-Aufruf
#         ans Substrat ist best-effort und nicht-blockierend — ein Substrat-
#         Ausfall darf den DB-Schreibpfad NIE blockieren (substrate_ref=NULL +
#         Log mit Emoji-Prefix).
#  Datenschutz: Rohe Readings gehen NICHT ans Substrat (Volumen) — nur diskrete
#         Ereignisse. Payload/Content tragen keine Klartext-PII (Personen-Felder
#         sind bereits tokenisiert).
# ============================================================
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import SemanticEvent
from foreman.substrate.client import SubstrateClient

logger = logging.getLogger("foreman.ingestion.semantic")

# Schlüssel, unter denen das Substrat eine Referenz/ID zurückgeben kann.
_REF_KEYS = ("id", "memory_id", "entry_id", "uuid", "ref", "result")


def extract_substrate_ref(data: dict[str, Any]) -> str | None:
    """Zieht eine Referenz-ID aus der Substrat-Antwort (erste passende Variante)."""
    for key in _REF_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
        # bool ist int-Subtyp — eine True/False-Referenz ist Unsinn, nie als ID werten.
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None


async def record_semantic_event(
    session: AsyncSession,
    *,
    machine_id: int | None,
    event_type: str,
    payload: dict[str, Any],
    content: str,
    substrate: SubstrateClient | None = None,
) -> SemanticEvent:
    """Schreibt eine semantic_events-Zeile und versucht best-effort den Dual-Write.

    Ablauf (nicht-blockierend): erst der remember-Versuch (in try/except gekapselt,
    Timeout über den httpx-Client), dann das Anlegen der Spiegel-Zeile mit der
    gewonnenen `substrate_ref` (oder NULL bei Fehlschlag/ohne Substrat). Die
    DB-Zeile entsteht IMMER — auch wenn das Substrat nicht erreichbar ist.
    """
    substrate_ref: str | None = None
    if substrate is not None:
        try:
            response = await substrate.remember(content, metadata=payload)
            substrate_ref = extract_substrate_ref(response)
            if substrate_ref is None:
                logger.warning(
                    "🧠 Substrat-remember ohne verwertbare Referenz (event_type=%s)",
                    event_type,
                )
            else:
                logger.info(
                    "✅ Substrat-Spiegel ok (event_type=%s, ref=%s)",
                    event_type,
                    substrate_ref,
                )
        except Exception as exc:
            logger.error(
                "❌ Substrat-Dual-Write fehlgeschlagen (event_type=%s): %s — "
                "Ereignis wird trotzdem in der DB gespiegelt (substrate_ref=NULL).",
                event_type,
                exc,
            )

    semantic_event = SemanticEvent(
        machine_id=machine_id,
        event_type=event_type,
        payload=payload,
        substrate_ref=substrate_ref,
    )
    session.add(semantic_event)
    return semantic_event
