# ============================================================
#  FOREMAN — archive/search.py
#  Zweck: Quellenübergreifende Archiv-Suche (Paket 1b) über drei Quellen:
#         - Notiz   : der 1a-Hybrid (Volltext + Vektor + RRF + Distanz-Cutoff,
#                     `embed_and_search_hybrid`) UNVERÄNDERT wiederverwendet.
#         - Wartung : NUR deutscher Volltext (`maintenance_events.text_tsv`).
#         - Alarm   : NUR deutscher Volltext (`alarms.text_tsv`).
#         Jede Quelle liefert eine Rangliste; global per RRF (k=60) zu einem Rang
#         fusioniert. Ergebnis = flache list[ArchiveHit] in globaler RRF-Reihenfolge.
#  Architektur-Einordnung: Schicht 2. Koppelt für den Notiz-Zweig nur an
#         `foreman.notes` (das 1a-Service-Surface), nie an eine Embedding-Library.
#  Verfügbarkeit: erbt die graceful degradation des Notiz-Zweigs — fällt das
#         Embedding-Backend aus, trägt dessen Volltext-Hälfte allein; Wartung/Alarm
#         (reiner Volltext) sind ohnehin unberührt. Kein 503, solange Volltext liefert.
#  Datenschutz (§8): `detail` PII-frei (kein HMAC-Token). Der Wartungs-/Alarm-Freitext
#         ist im Schreibpfad NICHT NER-maskiert (anders als Notiz-`text`) — er wird
#         hier so ausgeliefert wie gespeichert (Befund, nicht in 1b gelöst).
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.archive.schemas import ArchiveHit, SourceType
from foreman.core.sanitize import clean_excerpt
from foreman.db.models import Alarm, MaintenanceEvent, WorkerNote
from foreman.db.scope_sql import machine_scope_sql
from foreman.embeddings.provider import EmbeddingProvider
from foreman.notes.search import DEFAULT_SEARCH_K, RRF_K, embed_and_search_hybrid
from foreman.reasoners.event_chain.recall import (
    RecallItem,
    nur_sichtbare_treffer,
    recall_similar_incidents,
)
from foreman.substrate.client import SubstrateClient

# Alle Archiv-Quellen — Default-Suchraum, wenn `sources` nicht gesetzt ist.
ALL_SOURCES: tuple[SourceType, ...] = ("note", "maintenance", "alarm", "memory")

# Auszugs-Budget (Zeichen) — spiegelt frontend/lib/memory/excerpt.ts (Wortgrenze, " …").
EXCERPT_MAX = 180

# Ersatz-Zeitpunkt fuer eine Erinnerung ohne eigene Zeitangabe. Bewusst der
# Anfang der Zeitrechnung und nicht "jetzt": Ein Treffer ohne Zeit soll in einer
# zeitlich sortierten Liste HINTEN stehen, nicht faelschlich als der juengste.
_OHNE_ZEIT = datetime(1970, 1, 1, tzinfo=UTC)

# Allowlist der durchsuchbaren Volltext-Tabellen. `table` in `_fulltext_ids` wird per
# f-String interpoliert (Identifier sind nicht parametrisierbar); die Allowlist macht die
# Injection-Freiheit STRUKTURELL statt nur per Konvention (Defense-in-Depth, §16.1-Linie) —
# ein Aufrufer mit fremdem Wert bricht hart ab, statt SQL zu interpolieren.
_FULLTEXT_TABLES = frozenset({"maintenance_events", "alarms"})


def _make_excerpt(value: str | None, *, max_len: int = EXCERPT_MAX) -> str:
    """Kürzt Freitext auf einen Auszug an der Wortgrenze — spiegelt den 1a-Excerpt
    (frontend/lib/memory/excerpt.ts): Mehrfach-Whitespace zusammengezogen, an der
    letzten Wortgrenze im Budget geschnitten (nur ein überlanges Einzelwort hart),
    ' …'-Suffix. Entmaskiert nichts (NER-Marker wie [PERSON] bleiben erhalten).
    """
    normalized = " ".join((value or "").split())
    if len(normalized) <= max_len:
        return normalized
    cut = normalized[:max_len]
    last_space = cut.rfind(" ")
    base = cut[:last_space] if last_space > 0 else cut
    return f"{base.rstrip()} …"


async def _fulltext_ids(
    session: AsyncSession,
    table: str,
    q: str,
    *,
    machine_id: int | None,
    scope: Sequence[int] | None,
    k: int,
) -> list[int]:
    """Reiner Volltext-Rang (deutsche FTS) über `<table>.text_tsv` → ids in Rang-
    Reihenfolge. `table` MUSS in `_FULLTEXT_TABLES` liegen (per f-String interpoliert,
    da Identifier nicht parametrisierbar sind) — die Allowlist erzwingt die Injection-
    Freiheit strukturell. Ein Treffer IST per Definition ein Volltext-Match — kein
    Vektor-Zweig, kein Distanz-Cutoff (Wartung/Alarm tragen kein Embedding).
    """
    if table not in _FULLTEXT_TABLES:  # Defense-in-Depth: nie fremde Identifier interpolieren.
        raise ValueError(f"❌ Unbekannte Volltext-Tabelle: {table!r}")
    machine_filter, filter_params = machine_scope_sql(machine_id=machine_id, scope=scope)
    sql = f"""
        SELECT id
        FROM {table}
        WHERE text_tsv @@ websearch_to_tsquery('german', :q_text){machine_filter}
        ORDER BY ts_rank(text_tsv, websearch_to_tsquery('german', :q_text)) DESC, id ASC
        LIMIT :k
    """
    params: dict[str, object] = {"q_text": q, "k": k, **filter_params}
    result = await session.execute(text(sql), params)
    return [int(row_id) for row_id in result.scalars()]


async def _fetch_maintenance(session: AsyncSession, ids: list[int]) -> list[MaintenanceEvent]:
    """Lädt die Wartungsereignisse zu `ids` und bringt sie in die `ids`-Reihenfolge."""
    if not ids:
        return []
    rows = await session.scalars(select(MaintenanceEvent).where(MaintenanceEvent.id.in_(ids)))
    by_id = {event.id: event for event in rows}
    return [by_id[event_id] for event_id in ids if event_id in by_id]


async def _fetch_alarms(session: AsyncSession, ids: list[int]) -> list[Alarm]:
    """Lädt die Alarme zu `ids` und bringt sie in die `ids`-Reihenfolge."""
    if not ids:
        return []
    rows = await session.scalars(select(Alarm).where(Alarm.id.in_(ids)))
    by_id = {alarm.id: alarm for alarm in rows}
    return [by_id[alarm_id] for alarm_id in ids if alarm_id in by_id]


def _note_hit(note: WorkerNote) -> ArchiveHit:
    return ArchiveHit(
        source_type="note",
        id=note.id,
        machine_id=note.machine_id,
        timestamp=note.created_at,
        excerpt=_make_excerpt(note.text),
        detail={"shift": note.shift},
    )


def _maintenance_hit(event: MaintenanceEvent) -> ArchiveHit:
    return ArchiveHit(
        source_type="maintenance",
        id=event.id,
        machine_id=event.machine_id,
        timestamp=event.performed_at,
        excerpt=_make_excerpt(event.description),
        detail={"type": event.type},
    )


def _alarm_hit(alarm: Alarm) -> ArchiveHit:
    return ArchiveHit(
        source_type="alarm",
        id=alarm.id,
        machine_id=alarm.machine_id,
        timestamp=alarm.raised_at,
        excerpt=_make_excerpt(alarm.message),
        detail={"severity": alarm.severity, "category": alarm.category, "code": alarm.code},
    )


def _rrf_key(item: tuple[int, ArchiveHit]) -> tuple[float, float, str, int]:
    """Sortier-Schlüssel der globalen RRF-Fusion: höchster RRF-Score zuerst,
    deterministischer Tiebreaker (jüngster Zeitstempel, dann Quelle, dann id)."""
    rank, hit = item
    rrf_score = 1.0 / (RRF_K + rank)
    return (-rrf_score, -hit.timestamp.timestamp(), hit.source_type, hit.id)


def _quellzeile(hit: ArchiveHit) -> tuple[str, int] | None:
    """Auf welche Zeile der eigenen Datenbank ein Treffer zeigt.

    Bei den drei eigenen Quellen ist er selbst die Zeile. Eine Erinnerung zeigt
    über ihren Rückweg (`detail["quelle"]`, §12.4) auf eine — falls sie ihn
    kennt; Altbestand tut das nicht, dann `None`.
    """
    if hit.source_type != "memory":
        return (hit.source_type, hit.id)
    quelle = hit.detail.get("quelle")
    if isinstance(quelle, dict):
        art, kennung = quelle.get("art"), quelle.get("id")
        if isinstance(art, str) and art and isinstance(kennung, int) and kennung > 0:
            return (art, kennung)
    return None


def _ohne_doppelfunde(ranked: list[tuple[int, ArchiveHit]]) -> list[tuple[int, ArchiveHit]]:
    """Entfernt Erinnerungen, deren Quellzeile bereits als eigener Treffer dasteht.

    DASSELBE EREIGNIS, ZWEI RANGLISTEN: Eine Schichtnotiz ist über ihr Embedding
    als `note` auffindbar und über ihre Spiegelung als `memory`. Die Fusion sieht
    zwei getrennte Ströme und rangiert denselben Vorgang deshalb doppelt hoch —
    er verdrängt andere Treffer, ohne mehr zu sagen. Gemessen (25.08.2026):
    Die Auflösung hebt den Anteil zutreffender Treffer von 0,403 auf 0,445, ohne
    dass ein einziger relevanter Treffer verloren geht.

    DER EIGENE TREFFER BLEIBT, die Erinnerung fällt: Er ist die Quelle, sie die
    Ableitung. Er trägt die echte Kennung, seine Zeitangabe stammt aus der
    Datenbank statt aus dem Abruf, und sein Auszug ist der ungekürzte Originaltext.

    VOR DEM KÜRZEN, nicht danach: Sonst hinterliesse jede entfernte Dublette eine
    Lücke in der Liste, statt einen echten Treffer nachrücken zu lassen.

    Eine Erinnerung OHNE Rückweg bleibt unangetastet — sie könnte auf denselben
    Vorgang zeigen oder auf einen anderen; das ist nicht entscheidbar, und eine
    geratene Entfernung nähme dem Werker einen Treffer, den niemand geprüft hat.
    """
    eigene: set[tuple[str, int]] = {
        (hit.source_type, hit.id) for _rang, hit in ranked if hit.source_type != "memory"
    }
    behalten: list[tuple[int, ArchiveHit]] = []
    for rang, hit in ranked:
        zeile = _quellzeile(hit)
        if hit.source_type == "memory" and zeile is not None and zeile in eigene:
            continue
        behalten.append((rang, hit))
    return behalten


async def _substrat_treffer(
    substrate: SubstrateClient | None,
    q: str,
    *,
    machine_id: int | None,
    scope: Sequence[int] | None,
    k: int,
) -> list[ArchiveHit]:
    """Ruft Erinnerungen ab und formt sie zu ArchiveHits — STRIKT best-effort.

    Kein Substrat, abgeschaltet oder JEDER Fehler → leere Liste. Die drei eigenen
    Quellen tragen dann allein; das Archiv funktioniert ohne Gedächtnis weiter
    (dieselbe Zusage wie für den Embedding-Ausfall, §15.8).

    `machine_id` ist bei den eigenen Quellen ein harter WHERE-Filter. Hier kann er
    das nicht sein — der Abruf ist semantisch, nicht relational. Er wird deshalb
    NACHTRÄGLICH angewandt: ein Treffer ohne bekannte Maschine faellt bei gesetztem
    Filter heraus, statt als moeglicherweise passend durchzugehen. Lieber ein
    Treffer zu wenig als einer, der eine Zugehoerigkeit behauptet, die niemand
    geprueft hat.
    """
    if substrate is None or k <= 0:
        return []
    items = await recall_similar_incidents(substrate, q, max_results=k)

    # Der Rollen-Ausschnitt liegt in `nur_sichtbare_treffer` — EINE Quelle fuer alle
    # drei Stellen, die das Gedaechtnis befragen. Die Begruendung fuer die strenge
    # Auslegung (Treffer ohne bekannte Maschine fallen heraus) steht dort.
    sichtbar = nur_sichtbare_treffer(items, scope)
    treffer: list[ArchiveHit] = []
    for item in sichtbar:
        # Der Wunsch-Filter des Aufrufers wirkt zusaetzlich zum Ausschnitt.
        if machine_id is not None and item.machine_id != machine_id:
            continue
        treffer.append(_memory_hit(item))
    return treffer


def _memory_hit(item: RecallItem) -> ArchiveHit:
    """Formt eine Erinnerung zu einem Archiv-Treffer.

    Der Inhalt laeuft durch `clean_excerpt`, NICHT durch `_make_excerpt`: Er kommt
    aus dem Gedaechtnis zurueck und ist damit untrusted — HTML, Markdown-Links und
    rohe URLs werden entschaerft, nicht nur gekuerzt (Freigabe-Bedingung 5).

    `id` ist bei den eigenen Quellen der Primaerschluessel. Eine Erinnerung hat
    keinen; getragen wird stattdessen der Rueckweg in `detail` — falls die
    Erinnerung ihn kennt. Fuer Altbestand fehlt er und wird NICHT geraten.
    """
    detail: dict[str, Any] = {"herkunft": "gedaechtnis"}
    if item.ref:
        detail["erinnerung"] = item.ref
    if item.machine_class:
        detail["maschinenklasse"] = item.machine_class
    # DER RUECKWEG AUF DIE QUELLZEILE, falls die Erinnerung ihn kennt (§12.4).
    # Er steht im `detail` und NICHT in `source_type`/`id` des Treffers: Die
    # Herkunft bleibt sichtbar `memory` — als `maintenance` ausgegeben waere die
    # Erinnerung eine Behauptung ueber die eigene Datenlage, die nicht stimmt
    # ("Eigener Quelltyp, keine Tarnung", §15.10). Der Rueckweg sagt, WORAUF sie
    # sich bezieht, nicht WAS sie ist.
    #
    # WOZU (gemessen 25.08.2026, C-060): Ohne ihn ist ein Erinnerungs-Treffer
    # keiner Quellzeile zuzuordnen. Doppelfunde zwischen `note` und `memory`
    # bleiben dann unaufloesbar, und eine Guete-Messung kann einen solchen
    # Treffer rechnerisch nie als zutreffend werten.
    if item.source_type and item.source_id:
        detail["quelle"] = {"art": item.source_type, "id": item.source_id}

    return ArchiveHit(
        source_type="memory",
        # Kein Primaerschluessel vorhanden — 0 statt einer erfundenen Zahl, die
        # auf eine fremde Zeile zeigen wuerde. Der Rueckweg auf die Quellzeile
        # steht in `detail["quelle"]`, wenn die Erinnerung ihn kennt.
        id=0,
        machine_id=item.machine_id,
        # Ohne Zeitstempel waere der Treffer nicht einsortierbar; der Abruf liefert
        # ihn (Freigabe-Bedingung 4), und ohne ihn gehoert der Treffer nicht in
        # eine nach Zeit sortierbare Liste.
        timestamp=item.occurred_at or _OHNE_ZEIT,
        excerpt=clean_excerpt(item.content),
        detail=detail,
    )


async def search_archive(
    provider: EmbeddingProvider,
    session: AsyncSession,
    q: str,
    *,
    machine_id: int | None = None,
    scope: Sequence[int] | None = None,
    sources: Sequence[SourceType] | None = None,
    k: int = DEFAULT_SEARCH_K,
    max_distance: float,
    substrate: SubstrateClient | None = None,
    substrate_k: int = 0,
) -> list[ArchiveHit]:
    """Quellenübergreifende Archiv-Suche → flache list[ArchiveHit], Reihenfolge = RRF-Rang.

    `sources` wählt die Quellen (Teilmenge von note/maintenance/alarm; None = alle drei).
    `machine_id` (falls gesetzt) ist ein harter WHERE-Filter über ALLE gewählten Quellen.
    `scope` ist die Grenze der Rolle (§20.4) und wirkt über ALLE Quellen zugleich —
    jede einzelne muss ihn halten, sonst läge der Durchgriff in der Quelle, die
    niemand für sich geprüft hat.
    Notiz-Zweig = 1a-Hybrid (mit `max_distance`-Cutoff + graceful degradation),
    Wartung/Alarm = reiner Volltext. Jede Quelle liefert je bis zu `k` Kandidaten; die
    globale RRF-Fusion (k=60) interleavt sie fair nach quelleninternem Rang und schneidet
    auf `k`. KEIN Score-Feld nach außen.
    """
    selected = tuple(sources) if sources is not None else ALL_SOURCES
    # (quelleninterner 1-basierter Rang, Treffer) — über alle Quellen gesammelt.
    ranked: list[tuple[int, ArchiveHit]] = []

    if "note" in selected:
        notes = await embed_and_search_hybrid(
            provider,
            session,
            q,
            machine_id=machine_id,
            scope=scope,
            k=k,
            max_distance=max_distance,
        )
        ranked.extend((rank, _note_hit(note)) for rank, note in enumerate(notes, start=1))

    if "maintenance" in selected:
        ids = await _fulltext_ids(
            session, "maintenance_events", q, machine_id=machine_id, scope=scope, k=k
        )
        events = await _fetch_maintenance(session, ids)
        ranked.extend((rank, _maintenance_hit(event)) for rank, event in enumerate(events, start=1))

    if "alarm" in selected:
        ids = await _fulltext_ids(session, "alarms", q, machine_id=machine_id, scope=scope, k=k)
        alarms = await _fetch_alarms(session, ids)
        ranked.extend((rank, _alarm_hit(alarm)) for rank, alarm in enumerate(alarms, start=1))

    if "memory" in selected:
        erinnerungen = await _substrat_treffer(
            substrate, q, machine_id=machine_id, scope=scope, k=substrate_k
        )
        ranked.extend((rang, hit) for rang, hit in enumerate(erinnerungen, start=1))

    ranked.sort(key=_rrf_key)
    # Erst entdoppeln, DANN kürzen: Sonst hinterliesse jede entfernte Dublette
    # eine Lücke, statt einen echten Treffer nachrücken zu lassen.
    return [hit for _rank, hit in _ohne_doppelfunde(ranked)[:k]]
