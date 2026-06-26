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

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.archive.schemas import ArchiveHit, SourceType
from foreman.db.models import Alarm, MaintenanceEvent, WorkerNote
from foreman.embeddings.provider import EmbeddingProvider
from foreman.notes.search import DEFAULT_SEARCH_K, RRF_K, embed_and_search_hybrid

# Alle Archiv-Quellen — Default-Suchraum, wenn `sources` nicht gesetzt ist.
ALL_SOURCES: tuple[SourceType, ...] = ("note", "maintenance", "alarm")

# Auszugs-Budget (Zeichen) — spiegelt frontend/lib/memory/excerpt.ts (Wortgrenze, " …").
EXCERPT_MAX = 180

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
    session: AsyncSession, table: str, q: str, *, machine_id: int | None, k: int
) -> list[int]:
    """Reiner Volltext-Rang (deutsche FTS) über `<table>.text_tsv` → ids in Rang-
    Reihenfolge. `table` MUSS in `_FULLTEXT_TABLES` liegen (per f-String interpoliert,
    da Identifier nicht parametrisierbar sind) — die Allowlist erzwingt die Injection-
    Freiheit strukturell. Ein Treffer IST per Definition ein Volltext-Match — kein
    Vektor-Zweig, kein Distanz-Cutoff (Wartung/Alarm tragen kein Embedding).
    """
    if table not in _FULLTEXT_TABLES:  # Defense-in-Depth: nie fremde Identifier interpolieren.
        raise ValueError(f"❌ Unbekannte Volltext-Tabelle: {table!r}")
    machine_filter = " AND machine_id = :machine_id" if machine_id is not None else ""
    sql = f"""
        SELECT id
        FROM {table}
        WHERE text_tsv @@ websearch_to_tsquery('german', :q_text){machine_filter}
        ORDER BY ts_rank(text_tsv, websearch_to_tsquery('german', :q_text)) DESC, id ASC
        LIMIT :k
    """
    params: dict[str, object] = {"q_text": q, "k": k}
    if machine_id is not None:
        params["machine_id"] = machine_id
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


async def search_archive(
    provider: EmbeddingProvider,
    session: AsyncSession,
    q: str,
    *,
    machine_id: int | None = None,
    sources: Sequence[SourceType] | None = None,
    k: int = DEFAULT_SEARCH_K,
    max_distance: float,
) -> list[ArchiveHit]:
    """Quellenübergreifende Archiv-Suche → flache list[ArchiveHit], Reihenfolge = RRF-Rang.

    `sources` wählt die Quellen (Teilmenge von note/maintenance/alarm; None = alle drei).
    `machine_id` (falls gesetzt) ist ein harter WHERE-Filter über ALLE gewählten Quellen.
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
            provider, session, q, machine_id=machine_id, k=k, max_distance=max_distance
        )
        ranked.extend((rank, _note_hit(note)) for rank, note in enumerate(notes, start=1))

    if "maintenance" in selected:
        ids = await _fulltext_ids(session, "maintenance_events", q, machine_id=machine_id, k=k)
        events = await _fetch_maintenance(session, ids)
        ranked.extend((rank, _maintenance_hit(event)) for rank, event in enumerate(events, start=1))

    if "alarm" in selected:
        ids = await _fulltext_ids(session, "alarms", q, machine_id=machine_id, k=k)
        alarms = await _fetch_alarms(session, ids)
        ranked.extend((rank, _alarm_hit(alarm)) for rank, alarm in enumerate(alarms, start=1))

    ranked.sort(key=_rrf_key)
    return [hit for _rank, hit in ranked[:k]]
