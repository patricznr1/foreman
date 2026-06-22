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
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from foreman.db.models import Alarm, Machine
from foreman.logging_setup import REASON, get_logger
from foreman.reasoners.event_chain.schema import SiblingReference
from foreman.substrate.client import SubstrateClient

logger = get_logger("foreman.reasoners.event_chain.recall")

# Schlüssel, unter denen ein Recall-Ergebnis eine Trefferliste liefern kann.
_LIST_KEYS = ("results", "memories", "matches", "items", "hits", "data", "result")
# Schlüssel, unter denen der Inhalt eines Treffers stehen kann.
_CONTENT_KEYS = ("content", "text", "summary", "memory", "snippet", "value")
# Schlüssel, unter denen die Referenz/ID eines Treffers stehen kann.
_REF_KEYS = ("id", "memory_id", "entry_id", "uuid", "ref")
# Verschachtelte Container, in denen strukturierte Metadaten liegen können.
_META_KEYS = ("metadata", "payload", "meta")
# Schlüssel für die strukturierten Schwester-Bezüge (falls der Treffer sie trägt).
_MACHINE_ID_KEYS = ("machine_id", "machineId")
_MACHINE_CLASS_KEYS = ("machine_class", "machineClass")
_EXPLANATION_ID_KEYS = ("explanation_id", "explanationId")

# Output-Sanitisierung des Auszugs (LLM05, defensiv — der Recall-Inhalt ist
# untrusted externer Freitext und wird im FE nur angezeigt, nie als Instruktion).
_TAG_RE = re.compile(r"<[^>]*>")
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_URL_RE = re.compile(r"(?:https?|ftp|file|data|javascript|vbscript):(?://)?\S+", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")
_EXCERPT_MAX_LEN = 200


@dataclass(frozen=True)
class RecallItem:
    """Ein abgerufener ähnlicher Vergangenheits-Vorfall (untrusted Inhalt).

    `machine_id`/`machine_class`/`explanation_id` werden NUR gesetzt, wenn der reale
    Recall-Treffer sie trägt (z. B. aus dem gespiegelten `semantic_event`-Payload,
    §12.4) — sonst `None`. Sie sind die ehrliche Grundlage strukturierter
    Schwester-Referenzen; nichts wird erfunden.
    """

    content: str
    ref: str | None = None
    machine_id: int | None = None
    machine_class: str | None = None
    explanation_id: int | None = None


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


def _scopes(entry: dict[str, Any]) -> list[Mapping[str, Any]]:
    """Liefert die Such-Ebenen für strukturierte Felder: der Treffer selbst plus
    bekannte verschachtelte Container (`metadata`/`payload`/`meta`)."""
    scopes: list[Mapping[str, Any]] = [entry]
    for key in _META_KEYS:
        nested = entry.get(key)
        if isinstance(nested, dict):
            scopes.append(nested)
    return scopes


def _first_int(scopes: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> int | None:
    """Erste positive Ganzzahl unter den Schlüsseln (auch numerische Strings)."""
    for scope in scopes:
        for key in keys:
            value = scope.get(key)
            if isinstance(value, bool):  # bool ist int-Subtyp — nie als ID werten
                continue
            if isinstance(value, int) and value > 0:
                return value
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                parsed = int(value)
                if parsed > 0:
                    return parsed
    return None


def _first_str(scopes: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> str | None:
    """Erster nicht-leerer String unter den Schlüsseln."""
    for scope in scopes:
        for key in keys:
            value = scope.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _coerce_item(entry: Any) -> RecallItem | None:
    """Wandelt einen Roh-Treffer (str oder dict) in einen RecallItem (oder None).

    Strukturierte Schwester-Bezüge (machine_id/-class/explanation_id) werden
    defensiv aus dem Treffer und seinen Metadaten-Containern gezogen — und NUR
    gesetzt, wenn sie real vorhanden sind. Fehlen sie, bleiben sie `None`.
    """
    if isinstance(entry, str):
        text = entry.strip()
        return RecallItem(content=text) if text else None
    if isinstance(entry, dict):
        scopes = _scopes(entry)
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
            if isinstance(value, int) and not isinstance(value, bool):
                ref = str(value)
                break
        return RecallItem(
            content=content,
            ref=ref,
            machine_id=_first_int(scopes, _MACHINE_ID_KEYS),
            machine_class=_first_str(scopes, _MACHINE_CLASS_KEYS),
            explanation_id=_first_int(scopes, _EXPLANATION_ID_KEYS),
        )
    return None


def map_recall_response(data: dict[str, Any], *, max_results: int) -> list[RecallItem]:
    """Mappt die (normalisierte) Substrat-Antwort defensiv auf RecallItems.

    Sucht die erste Trefferliste unter den bekannten Schlüsseln und zieht je
    Eintrag Inhalt + optionale Referenz. Unbrauchbare Einträge werden übersprungen.
    """
    if max_results <= 0:
        return []
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
        # Mapping INNERHALB des try: ein unerwartetes Recall-Format (z. B. kein dict)
        # darf den best-effort-Vertrag nicht brechen → wird hier mitgefangen.
        return map_recall_response(data, max_results=max_results)
    except Exception as exc:
        # Bewusst breit (best-effort): JEDER Recall-Fehler → kein Recall, nie Abbruch.
        logger.warning("%s NEXUS-Recall fehlgeschlagen (best-effort, ohne Recall): %s", REASON, exc)
        return []


def to_grounding_inputs(items: Sequence[RecallItem]) -> list[str]:
    """Hilfs-Sicht: nur die Inhalte (für die Grounding-Quellen-Bildung)."""
    return [item.content for item in items]


def clean_excerpt(text: str, *, max_len: int = _EXCERPT_MAX_LEN) -> str:
    """Sanitisiert + kürzt den untrusted Recall-Inhalt für die reine Anzeige.

    Entfernt HTML/Markdown-Links/rohe URLs (Output-Smuggling, LLM05), normalisiert
    Whitespace und kürzt auf `max_len` (mit Ellipsis). Der Auszug ist NIE eine
    Instruktion — er wird im FE nur dargestellt.
    """
    cleaned = _MD_LINK_RE.sub(r"\1", text)
    cleaned = _TAG_RE.sub("", cleaned)
    cleaned = _URL_RE.sub("[link entfernt]", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1].rstrip() + "…"
    return cleaned


def sibling_similarity_basis(anchor: Alarm, machine: Machine | None) -> str:
    """Baut die ehrliche, PII-freie Ähnlichkeits-Basis (woran liegt die Ähnlichkeit).

    Es ist exakt die geteilte Anker-Signatur, auf die der Recall gematcht hat —
    Maschinenklasse + Alarm-Code + Kategorie (System-/SPS-Text, kein Werker-Freitext).
    """
    parts: list[str] = []
    if machine is not None and machine.machine_class:
        parts.append(f"Maschinenklasse {machine.machine_class}")
    if anchor.code:
        parts.append(f"Signatur {anchor.code}")
    if anchor.category:
        parts.append(f"Kategorie {anchor.category}")
    if not parts:
        return "ähnliches Vorfall-Muster"
    return "Ähnlich anhand: " + ", ".join(parts)


def build_sibling_references(
    items: Sequence[RecallItem],
    *,
    basis: str,
    class_by_machine: Mapping[int, str | None] | None = None,
    explanation_by_machine: Mapping[int, int | None] | None = None,
) -> list[SiblingReference]:
    """Formt reale Recall-Treffer zu strukturierten, EHRLICHEN Schwester-Referenzen.

    Reine Funktion: die DB-Auflösung (Maschinenklasse je `machine_id`, jüngste
    Schwester-Erklärung je `machine_id`) wird als fertige Maps injiziert — so ist
    die Form-Logik ohne Netz testbar. Strukturierte Ziele bleiben `None`, wenn weder
    der Treffer noch die Auflösung sie hergibt (kein erfundenes Geschwister). Leere
    Trefferliste → leere Referenz-Liste.
    """
    classes = class_by_machine or {}
    explanations = explanation_by_machine or {}
    siblings: list[SiblingReference] = []
    for item in items:
        machine_id = item.machine_id
        machine_class = item.machine_class
        if machine_id is not None and machine_class is None:
            machine_class = classes.get(machine_id)
        explanation_id = item.explanation_id
        if explanation_id is None and machine_id is not None:
            explanation_id = explanations.get(machine_id)
        siblings.append(
            SiblingReference(
                recall_ref=item.ref,
                machine_id=machine_id,
                machine_class=machine_class,
                explanation_id=explanation_id,
                similarity_basis=basis,
                excerpt=clean_excerpt(item.content),
            )
        )
    return siblings
