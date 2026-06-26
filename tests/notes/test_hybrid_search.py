# ============================================================
#  FOREMAN — tests/notes/test_hybrid_search.py
#  Zweck: Hybride Archiv-Suche (Paket 1a) gegen die ECHTE DB (pgvector/HNSW +
#         deutscher Volltext text_tsv/GIN, Migration 0012):
#         (1) EXAKTES WORT über den Volltext-Zweig gefunden (auch wenn der Vektor-
#             Zweig die Notiz nicht brächte), (2) RELEVANZ-CUTOFF verwirft ferne
#             Vektor-Treffer ohne Volltext-Match, (3) GRACEFUL DEGRADATION
#             (query_embedding None / Provider-Ausfall → Volltext trägt allein),
#             (4) machine_id-Filter greift hart in BEIDEN Zweigen.
#         Plus: text_tsv-Spalte + GIN-Index existieren. Query-Vektor konstruiert
#         (kein echtes Ollama).
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import Machine, WorkerNote
from foreman.embeddings.errors import ProviderUnavailable
from foreman.embeddings.provider import Vector
from foreman.notes import embed_and_search_hybrid, hybrid_search_notes

_DIM = 1024
# Cutoff für die Tests: deterministisch gesetzt (unabhängig vom Config-Default).
_MAX_DIST = 0.55


def _unit(index: int) -> Vector:
    """Einheitsvektor (1.0 an Position `index`, sonst 0) — L2-normiert."""
    vec = [0.0] * _DIM
    vec[index] = 1.0
    return vec


def _opposite() -> Vector:
    """Gegenvektor zu `_unit(0)` — Cosine-Distanz 2.0 (weit über jedem Cutoff)."""
    return [-1.0, *([0.0] * (_DIM - 1))]


# Query [1,0,0,…]. Cosine-Distanzen: identisch→0, orthogonal→1, gegen→2.
_QUERY = _unit(0)


class _FixedProvider:
    """EmbeddingProvider-Stub: liefert für jeden Text einen festen Vektor."""

    def __init__(self, vector: Vector) -> None:
        self._vector = vector

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        return [list(self._vector) for _ in texts]


class _FailProvider:
    """Simuliert ein nicht erreichbares Embedding-Backend (wirft EmbeddingError)."""

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        raise ProviderUnavailable("❌ kein Backend (Test)", attempted=("ollama",))


@pytest.mark.integration
async def test_hybrid_exaktes_wort_via_volltext_gefunden(db_session: AsyncSession) -> None:
    """(1) Notizen mit 'Fett'/'Beleuchtung' werden über den Volltext gefunden —
    auch wenn ihr Vektor sie (Gegenvektor, Distanz 2.0 ≫ Cutoff) nie brächte."""
    m = Machine(label="CNC-1", machine_class="cnc")
    db_session.add(m)
    await db_session.flush()
    # Exakt-Wort-Notizen mit Gegenvektor: rein vektoriell + Cutoff fielen sie raus.
    fett = WorkerNote(machine_id=m.id, text="Lager lief heiß, zu wenig Fett", embedding=_opposite())
    licht = WorkerNote(machine_id=m.id, text="Beleuchtung in Halle 2 defekt", embedding=_opposite())
    db_session.add_all([fett, licht])
    await db_session.flush()

    fett_hits = await hybrid_search_notes(
        db_session, "Fett", query_embedding=_QUERY, max_distance=_MAX_DIST, k=5
    )
    licht_hits = await hybrid_search_notes(
        db_session, "Beleuchtung", query_embedding=_QUERY, max_distance=_MAX_DIST, k=5
    )

    assert fett.id in [n.id for n in fett_hits]
    assert licht.id in [n.id for n in licht_hits]


@pytest.mark.integration
async def test_hybrid_cutoff_verwirft_fernen_vektortreffer(db_session: AsyncSession) -> None:
    """(2) Eine semantisch ferne Notiz OHNE Volltext-Match und über der Distanz-
    Schwelle wird NICHT zurückgegeben — der Cutoff ist die Ursache (nicht fehlender
    Match): mit großzügiger Schwelle käme dieselbe Notiz über den Vektor rein."""
    m = Machine(label="CNC-1", machine_class="cnc")
    db_session.add(m)
    await db_session.flush()
    # Distanz 1.0 (> 0.55), und der Text matcht die Query 'Schmierung' NICHT.
    fern = WorkerNote(machine_id=m.id, text="Beleuchtung in Halle erneuert", embedding=_unit(1))
    db_session.add(fern)
    await db_session.flush()

    streng = await hybrid_search_notes(
        db_session, "Schmierung", query_embedding=_QUERY, max_distance=_MAX_DIST, k=5
    )
    grosszuegig = await hybrid_search_notes(
        db_session, "Schmierung", query_embedding=_QUERY, max_distance=1.5, k=5
    )

    assert fern.id not in [n.id for n in streng]  # Cutoff greift
    assert fern.id in [n.id for n in grosszuegig]  # ohne Cutoff: Vektor-Treffer


@pytest.mark.integration
async def test_hybrid_graceful_ohne_vektor_nur_volltext(db_session: AsyncSession) -> None:
    """(3a) query_embedding None (Backend-Ausfall) → Volltext trägt allein; der
    exakte-Wort-Treffer bleibt erhalten, ein reiner Vektor-Nachbar fehlt mangels Vektor."""
    m = Machine(label="CNC-1", machine_class="cnc")
    db_session.add(m)
    await db_session.flush()
    fett = WorkerNote(machine_id=m.id, text="Spindel nachgefettet, Fett alt", embedding=_unit(1))
    nur_vektor = WorkerNote(machine_id=m.id, text="Beleuchtung getauscht", embedding=_QUERY)
    db_session.add_all([fett, nur_vektor])
    await db_session.flush()

    hits = await hybrid_search_notes(
        db_session, "Fett", query_embedding=None, max_distance=_MAX_DIST, k=5
    )
    ids = [n.id for n in hits]
    assert fett.id in ids  # Volltext-Treffer bleibt
    assert nur_vektor.id not in ids  # ohne Vektor-Zweig kein reiner Vektor-Treffer


@pytest.mark.integration
async def test_hybrid_graceful_provider_ausfall_komposition(db_session: AsyncSession) -> None:
    """(3b) embed_and_search_hybrid mit ausfallendem Provider wirft NICHT, sondern
    degradiert auf Volltext (kein Re-Raise, exakte-Wort-Treffer erhalten)."""
    m = Machine(label="CNC-1", machine_class="cnc")
    db_session.add(m)
    await db_session.flush()
    fett = WorkerNote(machine_id=m.id, text="Lager trocken, Fett fehlt", embedding=_unit(1))
    db_session.add(fett)
    await db_session.flush()

    hits = await embed_and_search_hybrid(
        _FailProvider(), db_session, "Fett", max_distance=_MAX_DIST, k=5
    )
    assert fett.id in [n.id for n in hits]


@pytest.mark.integration
async def test_hybrid_machine_id_filter_greift_in_beiden_zweigen(db_session: AsyncSession) -> None:
    """(4) machine_id filtert hart in BEIDEN Zweigen: eine Notiz mit Volltext- UND
    Vektor-Match auf der fremden Maschine taucht nicht auf."""
    m1 = Machine(label="CNC-1", machine_class="cnc")
    m2 = Machine(label="CNC-2", machine_class="cnc")
    db_session.add_all([m1, m2])
    await db_session.flush()
    # Beide identisch relevant (Volltext 'Fett' + Vektor = Query), nur Maschine unterscheidet.
    auf_m1 = WorkerNote(machine_id=m1.id, text="Lager Fett heiß", embedding=_QUERY)
    auf_m2 = WorkerNote(machine_id=m2.id, text="Lager Fett heiß", embedding=_QUERY)
    db_session.add_all([auf_m1, auf_m2])
    await db_session.flush()

    hits = await hybrid_search_notes(
        db_session, "Fett", query_embedding=_QUERY, machine_id=m2.id, max_distance=_MAX_DIST, k=5
    )
    assert [n.id for n in hits] == [auf_m2.id]  # nur Maschine 2, beide Zweige gefiltert


@pytest.mark.integration
async def test_text_tsv_index_und_spalte_existieren(raw_conn: asyncpg.Connection) -> None:
    """Migration 0012: generierte text_tsv-Spalte (deutsche FTS) + GIN-Index existieren."""
    col = await raw_conn.fetchrow(
        "SELECT is_generated, generation_expression FROM information_schema.columns "
        "WHERE table_name = 'worker_notes' AND column_name = 'text_tsv'"
    )
    assert col is not None
    assert col["is_generated"] == "ALWAYS"
    assert "to_tsvector" in col["generation_expression"].lower()
    assert "german" in col["generation_expression"].lower()

    idx = await raw_conn.fetchrow(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_worker_notes_text_tsv_gin'"
    )
    assert idx is not None
    indexdef = idx["indexdef"].lower()
    assert "gin" in indexdef
    assert "text_tsv" in indexdef
