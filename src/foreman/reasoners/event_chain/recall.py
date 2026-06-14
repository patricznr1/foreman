# ============================================================
#  FOREMAN — reasoners/event_chain/recall.py
#  Zweck: NEXUS-Recall ähnlicher Vergangenheits-Vorfälle (F6, Baustein 2) — die
#         „hatten wir das schon mal?"-Funktion. Bildet aus dem Anker-Muster
#         (Maschinenklasse + Drift-/Alarm-Signatur) eine Recall-Query und ruft
#         über den SubstrateClient ähnliche Vorfälle ab.
#  Architektur-Einordnung: Brücke Reasoning-Schicht → Substrat (GROUND_TRUTH §9).
#  Verhalten: STRIKT best-effort. Kein Substrat / Substrat-Ausfall blockiert den
#         Reasoner nie — die Kette wird dann ohne Recall-Anteil erzählt (leere
#         Liste). Logs ohne PII (die Query trägt nur Maschinenklasse/Code/Kategorie).
#  Sicherheit: Recall-Inhalte sind externer Freitext → in den Grounding-Quellen
#         werden sie als untrusted geführt (siehe grounding_sources.py).
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from foreman.db.models import Alarm, Machine
from foreman.logging_setup import REASON, get_logger
from foreman.substrate.client import SubstrateClient

logger = get_logger("foreman.reasoners.event_chain.recall")

# Schlüssel, unter denen ein Recall-Ergebnis eine Trefferliste liefern kann.
_LIST_KEYS = ("results", "memories", "matches", "items", "hits", "data", "result")
# Schlüssel, unter denen der Inhalt eines Treffers stehen kann.
_CONTENT_KEYS = ("content", "text", "summary", "memory", "snippet", "value")
# Schlüssel, unter denen die Referenz/ID eines Treffers stehen kann.
_REF_KEYS = ("id", "memory_id", "entry_id", "uuid", "ref")


@dataclass(frozen=True)
class RecallItem:
    """Ein abgerufener ähnlicher Vergangenheits-Vorfall (untrusted Inhalt)."""

    content: str
    ref: str | None = None


def build_recall_query(anchor: Alarm, machine: Machine | None) -> str:
    """Baut die Recall-Query aus dem Anker-Muster (PII-frei).

    Nutzt Maschinenklasse + Alarm-Code + Kategorie — keine Werker-Freitexte,
    keine Personen-/IDs mit Personenbezug. Fällt auf eine generische Formulierung
    zurück, wenn keine Merkmale vorliegen.
    """
    parts: list[str] = ["ähnlicher Vorfall"]
    if machine is not None and machine.machine_class:
        parts.append(f"Maschinenklasse {machine.machine_class}")
    if anchor.code:
        parts.append(f"Signatur {anchor.code}")
    if anchor.category:
        parts.append(f"Kategorie {anchor.category}")
    return " ".join(parts)


def _coerce_item(entry: Any) -> RecallItem | None:
    """Wandelt einen Roh-Treffer (str oder dict) in einen RecallItem (oder None)."""
    if isinstance(entry, str):
        text = entry.strip()
        return RecallItem(content=text) if text else None
    if isinstance(entry, dict):
        content: str | None = None
        for key in _CONTENT_KEYS:
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                content = value.strip()
                break
        if content is None:
            return None
        ref: str | None = None
        for key in _REF_KEYS:
            value = entry.get(key)
            if isinstance(value, str) and value:
                ref = value
                break
            if isinstance(value, int):
                ref = str(value)
                break
        return RecallItem(content=content, ref=ref)
    return None


def map_recall_response(data: dict[str, Any], *, max_results: int) -> list[RecallItem]:
    """Mappt die (normalisierte) Substrat-Antwort defensiv auf RecallItems.

    Sucht die erste Trefferliste unter den bekannten Schlüsseln und zieht je
    Eintrag Inhalt + optionale Referenz. Unbrauchbare Einträge werden übersprungen.
    """
    raw_list: list[Any] | None = None
    for key in _LIST_KEYS:
        value = data.get(key)
        if isinstance(value, list):
            raw_list = value
            break
    if raw_list is None:
        return []
    items: list[RecallItem] = []
    for entry in raw_list:
        item = _coerce_item(entry)
        if item is not None:
            items.append(item)
        if len(items) >= max_results:
            break
    return items


async def recall_similar_incidents(
    substrate: SubstrateClient | None,
    query: str,
    *,
    max_results: int = 5,
) -> list[RecallItem]:
    """Ruft ähnliche Vergangenheits-Vorfälle ab — STRIKT best-effort.

    Kein Substrat konfiguriert → leere Liste. Jeder Substrat-Fehler wird gefangen
    und führt zur leeren Liste (der Reasoner erzählt die Kette dann ohne
    Recall-Anteil). Es wird NIE eine Exception nach oben gereicht.
    """
    if substrate is None:
        return []
    try:
        data = await substrate.recall(query, max_results=max_results)
    except Exception as exc:
        logger.warning("%s NEXUS-Recall fehlgeschlagen (best-effort, ohne Recall): %s", REASON, exc)
        return []
    return map_recall_response(data, max_results=max_results)


def to_grounding_inputs(items: Sequence[RecallItem]) -> list[str]:
    """Hilfs-Sicht: nur die Inhalte (für die Grounding-Quellen-Bildung)."""
    return [item.content for item in items]
