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
from datetime import UTC, datetime
from html import unescape
from typing import Any

from foreman.core.sanitize import clean_excerpt
from foreman.db.models import Alarm, Machine
from foreman.ingestion.semantic import extract_substrate_ref
from foreman.logging_setup import REASON, get_logger
from foreman.observability.metrics import (
    RECALL_FEHLER,
    RECALL_LEER,
    RECALL_NICHT_KONFIGURIERT,
    RECALL_TREFFER,
    record_event_chain_recall,
)
from foreman.reasoners.event_chain.schema import SiblingReference
from foreman.substrate.client import SubstrateClient

logger = get_logger("foreman.reasoners.event_chain.recall")

# Schlüssel, unter denen ein Recall-Ergebnis eine Trefferliste liefern kann.
_LIST_KEYS = ("results", "memories", "matches", "items", "hits", "data", "result")
# Schlüssel, unter denen der Inhalt eines Treffers stehen kann.
_CONTENT_KEYS = ("content", "text", "summary", "memory", "snippet", "value")
# Treffer-Referenz/ID: geteilte, kanonische Extraktion (ingestion/semantic.py) —
# kein Duplikat (deckt id/memory_id/entry_id/uuid/ref/result + int, ohne bool).
# Verschachtelte Container, in denen strukturierte Metadaten liegen können.
_META_KEYS = ("metadata", "payload", "meta")
# Schlüssel für die strukturierten Schwester-Bezüge (falls der Treffer sie trägt).
_MACHINE_ID_KEYS = ("machine_id", "machineId")
_MACHINE_CLASS_KEYS = ("machine_class", "machineClass")
_EXPLANATION_ID_KEYS = ("explanation_id", "explanationId")
_SOURCE_TYPE_KEYS = ("source_type", "sourceType")
_SOURCE_ID_KEYS = ("source_id", "sourceId")
# Rang-Grundlage. Die Fassade liefert `relevance`; die generischen Namen decken
# andere Substrat-Fassungen ab, ohne dass hier etwas erfunden wird.
_RELEVANCE_KEYS = ("relevance", "score", "similarity", "relevance_score")
# Ereigniszeit des Treffers — WANN DER VORGANG WAR.
#
# Die Spiegelung schreibt sie in die Nutzlast: `performed_at` (Wartung),
# `raised_at` (Alarm), `started_at` (Produktionslauf), `created_at` (Notiz). Sie
# geht VOR, und zwar aus einem gemessenen Grund (27.08.2026): Die Fassade führt
# unter `occurred_at` den Zeitpunkt, zu dem die Erinnerung ANGELEGT wurde. Gegen
# die laufende Instanz erhoben trugen **19 von 19** Erinnerungs-Treffern damit
# ein Datum, dem ihr eigener Auszug direkt widersprach — angezeigt der 25.08.,
# im Text der Juni. Eine Trefferkarte, die das anzeigt, macht eine falsche
# Aussage über die eigene Datenlage; genau davor schützt der Schalter der
# vierten Quelle nicht, weil es kein Absturz ist, sondern eine stille Unwahrheit.
_EREIGNISZEIT_KEYS = (
    "performed_at",
    "raised_at",
    "started_at",
    "created_at",
    # `detected_at` gehört HIERHER, obwohl eine Abweichung eine Ableitung ist:
    # Es ist `sample.bucket` aus `readings_1m`, also der Zeitpunkt in der Halle,
    # an dem die Abweichung auftrat — nicht der des Rechnens. Der Drift-Reasoner
    # läuft ausschliesslich als Wiederholungslauf über historische Zeiträume
    # (`drift/runner.py::replay_machine`); die Zeit des Rechnens wäre für JEDEN
    # Befund eines Laufs dieselbe. Bis zum 28.08.2026 stand das Feld hier nicht,
    # und der Kommentar darunter behauptete, es gebe keins.
    "detected_at",
)
# Rückfallposition: die Gültigkeitszeit der Fassade. Sie trägt für die beiden
# Ableitungen OHNE eigenen Vorgangszeitpunkt — Ereigniskette und
# Ausfalleinschätzung führen `anchor_alarm_id` bzw. `prediction_id` und keine
# Zeit; wann sie abgeleitet wurden, IST ihre Zeit. Für die Abweichung gilt das
# NICHT (siehe `detected_at` oben).
_OCCURRED_AT_KEYS = ("occurred_at", "occurredAt", "timestamp", "createdAt")


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
    # Rangierbarkeit gegen einen ArchiveHit (Freigabe-Bedingung 4): ohne Zeit und
    # Ähnlichkeitsmaß lässt sich ein Substrat-Treffer nicht neben einen Treffer aus
    # der eigenen Datenbank stellen. Beides kommt aus dem realen Treffer oder bleibt
    # `None` — nichts wird geschätzt.
    occurred_at: datetime | None = None
    relevance: float | None = None
    # Rückweg auf die Quellzeile, aus der die Erinnerung entstand. Die
    # Spiegel-Nutzlast führt beides (§12.4) und geht als Metadaten mit; hier
    # kommt es zurück — falls der Treffer es trägt.
    #
    # WARUM ES GEBRAUCHT WIRD (gemessen 25.08.2026, C-060): Ohne diesen Rückweg
    # trägt ein Erinnerungs-Treffer im Archiv die Kennung 0 und ist keiner
    # Quellzeile zuzuordnen. Das hat zwei Wirkungen, die wie zwei Mängel
    # aussehen und einer sind: Doppelfunde zwischen `note` und `memory` lassen
    # sich nicht auflösen, UND eine Güte-Messung kann einen solchen Treffer
    # rechnerisch nie als zutreffend werten.
    #
    # ALTBESTAND TRÄGT ES NICHT: Zeilen aus der Zeit vor der Notiz-Spiegelung
    # kennen die Felder nicht. Dann bleibt es `None` — geraten wird nichts.
    source_type: str | None = None
    source_id: int | None = None


def nur_sichtbare_treffer(
    items: Sequence[RecallItem], scope: Sequence[int] | None
) -> list[RecallItem]:
    """Beschränkt Recall-Treffer auf den Maschinen-Ausschnitt des Anfragenden.

    WARUM DIESE FUNKTION EXISTIERT. Die Recall-Anfragen sind bewusst NICHT
    maschinenbezogen — sie suchen über Maschinenklasse, Signatur und Kategorie und
    treffen damit gerade die gleichartigen Maschinen ANDERER Linien. Das ist der
    fachliche Sinn der Sache: aus vergleichbaren Fällen lernen. Es heißt aber, dass
    die Antwort systematisch Fremdes enthält, und die Inhalte tragen die
    Maschinennummer im Klartext plus den gespiegelten Freitext.

    Der Ausschnitt wirkt hier NACHTRÄGLICH und mit derselben Strenge wie in der
    Archiv-Suche: Ein Treffer OHNE bekannte Maschine fällt für eine beschränkte
    Rolle heraus. Er könnte zu einer erlaubten gehören — belegt ist es nicht, und
    eine unbelegte Zugehörigkeit ist auf diesem Pfad kein Grund, ihn zu zeigen.

    `scope is None` heißt unbeschränkt (Manager, Techniker); `[]` heißt: nichts.

    EINE Quelle für alle drei Aufrufstellen — Archiv-Suche, Ereignisketten-Reasoner,
    Werker-Empfehlung. Getrennte Filter wären die Stelle, an der einer der Pfade
    zurückbliebe; genau das war der Fall, als nur die Archiv-Suche filterte.
    """
    if scope is None:
        return list(items)
    erlaubt = set(scope)
    return [item for item in items if item.machine_id in erlaubt]


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


def _first_float(scopes: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> float | None:
    """Erste endliche Fließkommazahl unter den Schlüsseln (auch numerische Strings).

    `bool` wird ausgeschlossen (int-Subtyp), ebenso NaN/Infinity: ein Rang, der
    sich nicht ordnen lässt, ist kein Rang.
    """
    for scope in scopes:
        for key in keys:
            value = scope.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int | float):
                zahl = float(value)
            elif isinstance(value, str) and value.strip():
                try:
                    zahl = float(value.strip())
                except ValueError:
                    continue
            else:
                continue
            if zahl == zahl and zahl not in (float("inf"), float("-inf")):
                return zahl
    return None


def _first_datetime(scopes: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> datetime | None:
    """Erster lesbarer ISO-8601-Zeitstempel unter den Schlüsseln, immer aware.

    Die Fassade liefert `occurred_at` OHNE Zeitzonen-Kennung. Ein naiver Wert
    ließe sich später nicht mit dem `timestamp` eines ArchiveHit vergleichen —
    Python wirft dabei `TypeError`, und zwar erst beim Sortieren, also weit weg
    von der Ursache. Er wird deshalb hier als UTC gelesen; das ist die Zeitachse,
    in der das Substrat schreibt.
    """
    for scope in scopes:
        for key in keys:
            value = scope.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            roh = value.strip().replace("Z", "+00:00")
            try:
                gelesen = datetime.fromisoformat(roh)
            except ValueError:
                continue
            return gelesen if gelesen.tzinfo is not None else gelesen.replace(tzinfo=UTC)
    return None


# Datenblock-Hülle der Gegenstelle. Sie zeichnet zurückgegebene Inhalte aus,
# damit ein lesendes Modell sie nicht als Anweisung nimmt — auf ihrer
# Werkzeug-Schnittstelle, und auf dem HTTP-Weg, sobald sie dort umgestellt ist. `.*` mit DOTALL, weil ein Inhalt Zeilenumbrüche tragen darf; Anker auf
# beiden Seiten, damit eine halbe Hülle NICHT greift (sonst liesse sich über
# einen abgeschnittenen Marker Inhalt unterschlagen).
_DATENBLOCK_RE = re.compile(r"\A\s*<tool_result_data[^>]*>(.*)</tool_result_data>\s*\Z", re.DOTALL)


def entpacke_datenblock(text: str) -> str:
    """Schält die Datenblock-Hülle ab, falls die Gegenstelle sie setzt.

    BEIDE ZUSTÄNDE MÜSSEN TRAGEN: Ohne Hülle bleibt der Text unverändert. Nur so
    kann die Gegenstelle ihren Schalter umlegen, ohne dass hier etwas bricht —
    dieselbe Logik wie beim Schalter der vierten Archiv-Quelle (§15.10).

    ABGESCHÄLT, NICHT ALS SCHUTZ GEWERTET: Die Markierung richtet sich an ein
    Modell, das den Rohtext direkt liest. FOREMAN baut seinen Prompt selbst und
    führt Abruf-Treffer über `grounding_sources.py` als `trusted=False` mit
    eigenem Spotlighting. Die fremde Hülle bliebe im Auszug stehen und stünde am
    Ende in der Trefferliste eines Werkers — sie gehört heraus.

    Der Inhalt ist in der Hülle maskiert; ohne Rückwandlung stünde "&lt;" im Text.
    """
    treffer = _DATENBLOCK_RE.match(text)
    if treffer is None:
        return text
    return unescape(treffer.group(1)).strip()


def _coerce_item(entry: Any) -> RecallItem | None:
    """Wandelt einen Roh-Treffer (str oder dict) in einen RecallItem (oder None).

    Strukturierte Schwester-Bezüge (machine_id/-class/explanation_id) werden
    defensiv aus dem Treffer und seinen Metadaten-Containern gezogen — und NUR
    gesetzt, wenn sie real vorhanden sind. Fehlen sie, bleiben sie `None`.
    """
    if isinstance(entry, str):
        text = entpacke_datenblock(entry).strip()
        return RecallItem(content=text) if text else None
    if isinstance(entry, dict):
        scopes = _scopes(entry)
        content: str | None = None
        for key in _CONTENT_KEYS:
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                content = entpacke_datenblock(value).strip()
                break
        if content is None:
            return None
        ref = extract_substrate_ref(entry)
        return RecallItem(
            content=content,
            ref=ref,
            machine_id=_first_int(scopes, _MACHINE_ID_KEYS),
            machine_class=_first_str(scopes, _MACHINE_CLASS_KEYS),
            explanation_id=_first_int(scopes, _EXPLANATION_ID_KEYS),
            occurred_at=(
                _first_datetime(scopes, _EREIGNISZEIT_KEYS)
                or _first_datetime(scopes, _OCCURRED_AT_KEYS)
            ),
            relevance=_first_float(scopes, _RELEVANCE_KEYS),
            source_type=_first_str(scopes, _SOURCE_TYPE_KEYS),
            source_id=_first_int(scopes, _SOURCE_ID_KEYS),
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
        record_event_chain_recall(RECALL_NICHT_KONFIGURIERT)
        return []
    try:
        data = await substrate.recall(query, max_results=max_results)
        # Mapping INNERHALB des try: ein unerwartetes Recall-Format (z. B. kein dict)
        # darf den best-effort-Vertrag nicht brechen → wird hier mitgefangen.
        treffer = map_recall_response(data, max_results=max_results)
    except Exception as exc:
        # Bewusst breit (best-effort): JEDER Recall-Fehler → kein Recall, nie Abbruch.
        record_event_chain_recall(RECALL_FEHLER)
        logger.warning("%s NEXUS-Recall fehlgeschlagen (best-effort, ohne Recall): %s", REASON, exc)
        return []
    # Erst NACH dem try zählen: ein Fehler im Zähler selbst würde sonst als
    # Recall-Fehler verbucht und die Quote verfälschen.
    record_event_chain_recall(RECALL_TREFFER if treffer else RECALL_LEER)
    return treffer


def to_grounding_inputs(items: Sequence[RecallItem]) -> list[str]:
    """Hilfs-Sicht: nur die Inhalte (für die Grounding-Quellen-Bildung)."""
    return [item.content for item in items]


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
