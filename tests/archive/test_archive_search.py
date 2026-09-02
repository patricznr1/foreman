# ============================================================
#  FOREMAN — tests/archive/test_archive_search.py
#  Zweck: Quellenübergreifende Archiv-Suche (Paket 1b) gegen die ECHTE DB:
#         (1) QUELLEN-FILTER (note/maintenance/Default alle), (2) MULTI-QUELLE
#         ("Fett" über Notiz UND Wartung, korrekt typisiert), (3) machine_id-Filter
#         hart über alle drei Quellen, (4) VOLLTEXT-ONLY-DISZIPLIN (kein Auffüllen)
#         + ArchiveHit.detail PII-frei (kein HMAC-Token). Plus Excerpt-Wortgrenze,
#         Index-Existenz, graceful degradation bei Provider-Ausfall.
#         Query-Vektor konstruiert (kein echtes Ollama).
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.archive import search_archive
from foreman.db.models import Alarm, Machine, MaintenanceEvent, WorkerNote
from foreman.embeddings.config import EmbeddingMode
from foreman.embeddings.errors import ProviderUnavailable
from foreman.embeddings.provider import Vector

_DIM = 1024
_MAX_DIST = 0.55
_HMAC = "v1:" + "a" * 64  # token-förmiger Platzhalter (nie in detail erwartet)


def _unit(index: int) -> Vector:
    vec = [0.0] * _DIM
    vec[index] = 1.0
    return vec


_QUERY = _unit(0)


class _FixedProvider:
    def __init__(self, vector: Vector) -> None:
        self._vector = vector

    async def embed(self, texts: Sequence[str], *, mode: EmbeddingMode = "passage") -> list[Vector]:
        return [list(self._vector) for _ in texts]


class _FailProvider:
    async def embed(self, texts: Sequence[str], *, mode: EmbeddingMode = "passage") -> list[Vector]:
        raise ProviderUnavailable("❌ kein Backend (Test)", attempted=("ollama",))


def _provider() -> _FixedProvider:
    return _FixedProvider(_QUERY)


@pytest.mark.integration
async def test_quellen_filter_und_default(db_session: AsyncSession) -> None:
    """(1) sources=[maintenance] nur Wartung; [note] nur Notiz (1a-Hybrid); Default alle drei."""
    m = Machine(label="CNC-1", machine_class="cnc")
    db_session.add(m)
    await db_session.flush()
    note = WorkerNote(machine_id=m.id, text="Lager mit Fett geschmiert", embedding=_unit(0))
    maint = MaintenanceEvent(machine_id=m.id, type="lubrication", description="Fett nachgefüllt")
    alarm = Alarm(
        machine_id=m.id, severity="warning", category="process", code="LUB-1", message="Fett knapp"
    )
    db_session.add_all([note, maint, alarm])
    await db_session.flush()

    only_maint = await search_archive(
        _provider(), db_session, "Fett", sources=["maintenance"], max_distance=_MAX_DIST, k=10
    )
    only_note = await search_archive(
        _provider(), db_session, "Fett", sources=["note"], max_distance=_MAX_DIST, k=10
    )
    all_sources = await search_archive(
        _provider(), db_session, "Fett", sources=None, max_distance=_MAX_DIST, k=10
    )

    assert only_maint and all(h.source_type == "maintenance" for h in only_maint)
    assert maint.id in [h.id for h in only_maint]
    assert only_note and all(h.source_type == "note" for h in only_note)
    assert note.id in [h.id for h in only_note]
    assert {h.source_type for h in all_sources} == {"note", "maintenance", "alarm"}


@pytest.mark.integration
async def test_multi_quelle_korrekt_typisiert(db_session: AsyncSession) -> None:
    """(2) "Fett" findet sowohl eine Notiz als auch ein Wartungsprotokoll, korrekt typisiert."""
    m = Machine(label="CNC-1", machine_class="cnc")
    db_session.add(m)
    await db_session.flush()
    note = WorkerNote(machine_id=m.id, text="Spindel nachgefettet, Fett alt", embedding=_unit(1))
    maint = MaintenanceEvent(machine_id=m.id, type="lubrication", description="Fett erneuert")
    db_session.add_all([note, maint])
    await db_session.flush()

    hits = await search_archive(_provider(), db_session, "Fett", max_distance=_MAX_DIST, k=10)
    note_hit = next(h for h in hits if h.source_type == "note")
    maint_hit = next(h for h in hits if h.source_type == "maintenance")
    assert note_hit.id == note.id
    assert maint_hit.id == maint.id
    assert maint_hit.detail == {"type": "lubrication"}


@pytest.mark.integration
async def test_machine_id_filter_alle_quellen(db_session: AsyncSession) -> None:
    """(3) machine_id filtert hart über alle drei Quellen."""
    m1 = Machine(label="CNC-1", machine_class="cnc")
    m2 = Machine(label="CNC-2", machine_class="cnc")
    db_session.add_all([m1, m2])
    await db_session.flush()
    n1 = WorkerNote(machine_id=m1.id, text="Fett", embedding=_unit(0))
    n2 = WorkerNote(machine_id=m2.id, text="Fett", embedding=_unit(0))
    mt1 = MaintenanceEvent(machine_id=m1.id, type="lubrication", description="Fett")
    mt2 = MaintenanceEvent(machine_id=m2.id, type="lubrication", description="Fett")
    al1 = Alarm(machine_id=m1.id, severity="warning", category="process", message="Fett")
    al2 = Alarm(machine_id=m2.id, severity="warning", category="process", message="Fett")
    db_session.add_all([n1, n2, mt1, mt2, al1, al2])
    await db_session.flush()

    hits = await search_archive(
        _provider(), db_session, "Fett", machine_id=m2.id, max_distance=_MAX_DIST, k=20
    )
    assert all(h.machine_id == m2.id for h in hits)
    found = {(h.source_type, h.id) for h in hits}
    assert {("note", n2.id), ("maintenance", mt2.id), ("alarm", al2.id)} <= found
    assert not ({("note", n1.id), ("maintenance", mt1.id), ("alarm", al1.id)} & found)


@pytest.mark.integration
async def test_volltext_only_disziplin_und_detail_pii_frei(db_session: AsyncSession) -> None:
    """(4) Wartung/Alarm ohne Volltext-Match werden NICHT zurückgegeben (kein Auffüllen);
    ArchiveHit.detail ist PII-frei (kein HMAC-Token)."""
    m = Machine(label="CNC-1", machine_class="cnc")
    db_session.add(m)
    await db_session.flush()
    alarm = Alarm(
        machine_id=m.id,
        severity="warning",
        category="process",
        code="ILL-7",
        message="Beleuchtung in Halle 2 defekt",
        acknowledged_by=_HMAC,
    )
    maint = MaintenanceEvent(
        machine_id=m.id, type="inspection", description="Schmierung geprüft", performed_by=_HMAC
    )
    db_session.add_all([alarm, maint])
    await db_session.flush()

    hits = await search_archive(
        _provider(), db_session, "Beleuchtung", max_distance=_MAX_DIST, k=10
    )
    found = {(h.source_type, h.id) for h in hits}
    assert ("alarm", alarm.id) in found  # Volltext-Match
    assert ("maintenance", maint.id) not in found  # kein Match → kein Auffüllen

    alarm_hit = next(h for h in hits if h.source_type == "alarm")
    assert alarm_hit.detail == {"severity": "warning", "category": "process", "code": "ILL-7"}
    assert "acknowledged_by" not in alarm_hit.detail
    assert all(value != _HMAC for value in alarm_hit.detail.values())


@pytest.mark.integration
async def test_graceful_degradation_provider_ausfall(db_session: AsyncSession) -> None:
    """Provider-Ausfall: Notiz-Zweig degradiert auf Volltext, Wartung/Alarm unberührt — kein Fehler."""
    m = Machine(label="CNC-1", machine_class="cnc")
    db_session.add(m)
    await db_session.flush()
    note = WorkerNote(machine_id=m.id, text="Lager Fett alt", embedding=_unit(1))
    maint = MaintenanceEvent(machine_id=m.id, type="lubrication", description="Fett")
    alarm = Alarm(machine_id=m.id, severity="warning", category="process", message="Fett")
    db_session.add_all([note, maint, alarm])
    await db_session.flush()

    hits = await search_archive(_FailProvider(), db_session, "Fett", max_distance=_MAX_DIST, k=10)
    assert {"note", "maintenance", "alarm"} <= {h.source_type for h in hits}


@pytest.mark.integration
async def test_excerpt_an_wortgrenze_gekuerzt(db_session: AsyncSession) -> None:
    """Excerpt spiegelt den 1a-Mechanismus: an der Wortgrenze gekürzt, ' …'-Suffix."""
    m = Machine(label="CNC-1", machine_class="cnc")
    db_session.add(m)
    await db_session.flush()
    long_text = "Fett " + "Wort " * 80  # weit über dem 180-Zeichen-Budget
    note = WorkerNote(machine_id=m.id, text=long_text, embedding=_unit(0))
    db_session.add(note)
    await db_session.flush()

    hits = await search_archive(
        _provider(), db_session, "Fett", sources=["note"], max_distance=_MAX_DIST, k=5
    )
    excerpt = hits[0].excerpt
    assert excerpt.endswith(" …")
    assert len(excerpt) <= 182  # 180-Budget an Wortgrenze + " …"
    assert "  " not in excerpt  # Mehrfach-Whitespace zusammengezogen


@pytest.mark.integration
async def test_text_tsv_indizes_existieren(raw_conn: asyncpg.Connection) -> None:
    """Migration 0013: generierte text_tsv-Spalten + GIN-Indizes für beide Quellen."""
    for table, index_name in (
        ("maintenance_events", "ix_maintenance_events_text_tsv_gin"),
        ("alarms", "ix_alarms_text_tsv_gin"),
    ):
        col = await raw_conn.fetchrow(
            "SELECT is_generated, generation_expression FROM information_schema.columns "
            "WHERE table_name = $1 AND column_name = 'text_tsv'",
            table,
        )
        assert col is not None
        assert col["is_generated"] == "ALWAYS"
        assert "german" in col["generation_expression"].lower()
        idx = await raw_conn.fetchrow(
            "SELECT indexdef FROM pg_indexes WHERE indexname = $1", index_name
        )
        assert idx is not None
        assert "gin" in idx["indexdef"].lower()


@pytest.mark.integration
async def test_fulltext_ids_lehnt_unbekannte_tabelle_ab(db_session: AsyncSession) -> None:
    """Defense-in-Depth: _fulltext_ids interpoliert nie einen fremden Identifier (Allowlist)."""
    from foreman.archive.search import _fulltext_ids

    with pytest.raises(ValueError):
        await _fulltext_ids(db_session, "users; DROP TABLE", "x", machine_id=None, scope=None, k=5)


class _SubstratMit:
    """Gegenstelle, die genau eine Erinnerung liefert — mit Rückweg auf eine Zeile."""

    def __init__(self, *, art: str, kennung: int, machine_id: int) -> None:
        self._art, self._kennung, self._machine_id = art, kennung, machine_id

    # ACHTUNG, hier ist schon einmal etwas auseinandergelaufen: Diese Attrappe
    # bildet die Signatur des echten Klienten VON HAND nach. Kommt dort ein
    # Feld dazu, bricht der Aufruf hier — und der best-effort-Vertrag von
    # `recall_similar_incidents` VERSCHLUCKT den Bruch: Der Abruf liefert still
    # eine leere Liste, der Test wird rot an einer ganz anderen Zusicherung.
    # Die Nachbartests (test_recall.py, test_substrat_veredelung.py) fahren
    # deshalb den ECHTEN Klienten gegen einen httpx.MockTransport. Wer diese
    # Datei ohnehin anfasst, sollte sie dorthin ziehen.
    async def recall(
        self, query: str, *, max_results: int = 5, correlation_id: str | None = None
    ) -> dict:
        return {
            "results": [
                {
                    "id": "aaaaaaaa-0000-0000-0000-000000000001",
                    "content": "Wartung (lubrication) an Maschine X. Fett nachgefüllt.",
                    "relevance": 0.9,
                    "occurred_at": "2026-06-24T09:00:00+00:00",
                    "metadata": {
                        "machine_id": self._machine_id,
                        "source_type": self._art,
                        "source_id": self._kennung,
                    },
                }
            ]
        }


@pytest.mark.integration
async def test_derselbe_vorgang_steht_nur_einmal_in_der_liste(db_session: AsyncSession) -> None:
    """Die VERDRAHTUNG der Doppelfund-Auflösung, nicht die Funktion.

    ANLASS: Zwei Gegenproben — die Auflösung aus der Fusion herausnehmen und sie
    hinter das Kürzen ziehen — blieben grün, weil jeder Test die Hilfsfunktion
    direkt aufrief. Eine getestete Funktion, die niemand aufruft, ist so
    wirkungslos wie eine fehlende; geprüft werden muss der Weg, den die Anfrage
    tatsächlich nimmt.

    Aufbau: Ein Wartungsvorgang liegt in der Datenbank, und die Gegenstelle
    liefert eine Erinnerung, die über ihren Rückweg auf genau diesen Vorgang
    zeigt. Ohne Auflösung stünde er zweimal in der Liste.
    """
    m = Machine(label="AX-02", machine_class="servo_axis")
    db_session.add(m)
    await db_session.flush()
    maint = MaintenanceEvent(machine_id=m.id, type="lubrication", description="Fett nachgefüllt")
    db_session.add(maint)
    await db_session.flush()

    hits = await search_archive(
        _provider(),
        db_session,
        "Fett",
        max_distance=_MAX_DIST,
        k=10,
        substrate=_SubstratMit(art="maintenance", kennung=maint.id, machine_id=m.id),
        substrate_k=5,
    )

    schluessel = [(h.source_type, h.id) for h in hits]
    assert ("maintenance", maint.id) in schluessel, "der eigene Treffer fehlt"
    assert not [h for h in hits if h.source_type == "memory"], (
        "der Vorgang steht zweimal in der Liste — die Auflösung greift nicht"
    )


@pytest.mark.integration
async def test_erinnerung_auf_einen_unbekannten_vorgang_bleibt(db_session: AsyncSession) -> None:
    """AUFBAU-KONTROLLE: Ohne sie wäre 'die Erinnerung fällt weg' auch mit
    'Erinnerungen fallen immer weg' erklärbar — und der Gewinn der vierten
    Quelle wäre still verschwunden."""
    m = Machine(label="AX-03", machine_class="servo_axis")
    db_session.add(m)
    await db_session.flush()
    maint = MaintenanceEvent(machine_id=m.id, type="lubrication", description="Fett nachgefüllt")
    db_session.add(maint)
    await db_session.flush()

    hits = await search_archive(
        _provider(),
        db_session,
        "Fett",
        max_distance=_MAX_DIST,
        k=10,
        # Zeigt auf eine Zeile, die die Suche NICHT gefunden hat.
        substrate=_SubstratMit(art="maintenance", kennung=maint.id + 9999, machine_id=m.id),
        substrate_k=5,
    )

    assert [h for h in hits if h.source_type == "memory"], (
        "die Erinnerung wurde zu Unrecht entfernt"
    )
