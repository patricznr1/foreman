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

from foreman.db.models import SemanticEvent, WorkerNote
from foreman.substrate.client import SubstrateClient
from foreman.substrate.content import baue_inhalt

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


def notiz_payload(note: WorkerNote, masked_text: str) -> dict[str, object]:
    """Baut die Spiegel-Nutzlast einer Schichtnotiz — für BEIDE Schreibwege.

    Der `author` bleibt bewusst DRAUSSEN, obwohl die Wartung ihr `performed_by`
    mitschickt. Bei der Wartung ist die ausführende Rolle Teil des Nachweises;
    für die Frage "hatten wir das schon mal" trägt der Verfasser nichts bei.
    Datensparsamkeit schlägt Symmetrie — ein Pseudonym, das keine Frage
    beantwortet, gehört nicht an einen zweiten Ort.

    `text` ist der NER-maskierte Text. Beide Schreibwege maskieren vor dem
    Insert; diese Funktion bekommt ihn übergeben statt ihn aus dem Objekt zu
    lesen, damit die Herkunft an der Aufrufstelle sichtbar bleibt.
    """
    return {
        "machine_id": note.machine_id,
        "shift": note.shift,
        "text": masked_text,
        "created_at": note.created_at.isoformat(),
        "source_type": "note",
        "source_id": note.id,
    }


async def record_semantic_event(
    session: AsyncSession,
    *,
    machine_id: int | None,
    event_type: str,
    payload: dict[str, Any],
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
            # Der Text wird aus der payload GEBAUT, nicht vom Aufrufer mitgegeben
            # (Befund 20.08.2026): Vorher schrieb ihn jeder Aufrufer selbst hin, und der
            # nachtraegliche Backfill fuehrte eine zweite Fassung derselben Saetze. Zusammen
            # gehalten wurden sie von einem Kommentar und von keinem Test. Jetzt gibt es
            # nur noch eine Quelle (substrate/content.py) — Abweichung ist strukturell
            # ausgeschlossen statt bloss unerwuenscht.
            #
            # INNERHALB des try (seit 24.08.2026): Vorher lag der Aufruf davor. Ein
            # unbekannter event_type oder ein fehlendes Pflichtfeld warf damit aus
            # dieser Funktion heraus und riss den Insert des AUFRUFERS mit — beim
            # Werker-Notiz-Pfad waere das der Kernpfad der Halle gewesen. Der Text
            # wird ohnehin nur fuer die Spiegelung gebraucht; scheitert sein Bau,
            # ist das derselbe Fall wie ein nicht erreichbares Substrat.
            content = baue_inhalt(event_type, payload)
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
                "Ereignis wird trotzdem in der DB gespiegelt (substrate_ref=NULL). "
                "Ein KeyError zeigt hier auf die Formulierung, nicht auf das Netz: "
                "unbekannter event_type oder fehlendes Pflichtfeld in der payload.",
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
