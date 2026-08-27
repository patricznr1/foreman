# ============================================================
#  FOREMAN — tests/embeddings/test_backfill.py
#  Zweck: Backfill-Runner (F-SEM, Baustein 2) gegen die ECHTE DB — nur NULL-Zeilen,
#         Idempotenz (zweiter Lauf findet nichts), Batch-Verarbeitung. Provider über
#         das Mock-Backend (kein echtes Ollama).
# ============================================================
from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import WorkerNote
from foreman.embeddings import LocalEmbeddingProvider
from foreman.embeddings.backfill import backfill_embeddings

MakeProvider = Callable[..., LocalEmbeddingProvider]
MakeBackend = Callable[..., object]


async def _null_count(session: AsyncSession) -> int:
    stmt = select(func.count()).select_from(WorkerNote).where(WorkerNote.embedding.is_(None))
    return int((await session.scalar(stmt)) or 0)


async def _seed_notes(session: AsyncSession, n_without: int, *, n_with: int = 0) -> None:
    for i in range(n_without):
        session.add(WorkerNote(text=f"Notiz ohne Embedding {i}", shift="frueh"))
    for i in range(n_with):
        # Bereits embeddete Notiz (darf NICHT erneut angefasst werden).
        session.add(WorkerNote(text=f"Notiz mit Embedding {i}", embedding=[0.0] * 1024))
    await session.commit()


@pytest.mark.integration
async def test_backfill_embeddet_nur_null_zeilen(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    await _seed_notes(db_session, n_without=2, n_with=1)
    provider = make_provider(
        backends=[make_embed_backend("ollama", dim=1024)], priority="ollama_only"
    )

    written = await backfill_embeddings(db_session, provider, batch_size=10)

    assert written == 2  # nur die zwei NULL-Zeilen, nicht die bereits embeddete
    assert await _null_count(db_session) == 0


@pytest.mark.integration
async def test_backfill_ist_idempotent(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    await _seed_notes(db_session, n_without=3)
    provider = make_provider(
        backends=[make_embed_backend("ollama", dim=1024)], priority="ollama_only"
    )

    first = await backfill_embeddings(db_session, provider, batch_size=10)
    second = await backfill_embeddings(db_session, provider, batch_size=10)

    assert first == 3
    assert second == 0  # zweiter Lauf findet nichts mehr


@pytest.mark.integration
async def test_backfill_verarbeitet_in_batches(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    await _seed_notes(db_session, n_without=5)
    backend = make_embed_backend("ollama", dim=1024)
    provider = make_provider(backends=[backend], priority="ollama_only")

    written = await backfill_embeddings(db_session, provider, batch_size=2)

    assert written == 5
    # 5 Notizen / Batch 2 → 3 Batch-Calls (2 + 2 + 1).
    assert backend.calls == 3  # type: ignore[attr-defined]


@pytest.mark.integration
async def test_backfill_lehnt_batch_size_kleiner_eins_ab(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    provider = make_provider(
        backends=[make_embed_backend("ollama", dim=1024)], priority="ollama_only"
    )
    with pytest.raises(ValueError, match="batch_size"):
        await backfill_embeddings(db_session, provider, batch_size=0)


# ──────────────────────────────────────────────────────────────────────
#  Neu einbetten — was ein Modellwechsel braucht
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_alle_neu_bettet_auch_vorhandene_vektoren_neu_ein(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    """Der Fall, für den `nur_fehlende=False` existiert: ein Modellwechsel.

    Vektoren verschiedener Modelle liegen in verschiedenen Räumen. Bleiben alte
    stehen, vergleicht die Suche Unvergleichbares — und liefert plausibel
    aussehenden Unsinn, ohne Fehler und ohne Warnung.
    """
    await _seed_notes(db_session, n_without=0, n_with=3)
    provider = make_provider(
        backends=[make_embed_backend("ollama", dim=1024)], priority="ollama_only"
    )

    # MIT ZEITSCHRANKE wie der Terminierungs-Fall: JEDER Lauf mit
    # `nur_fehlende=False` kann bei einem Fehler in der Blätterung endlos drehen.
    # Ohne die Schranke hinge dieser Test mit — und ein hängender Test sagt nicht,
    # WAS kaputt ist. Belegt am 27.08.2026: Die Gegenprobe lief in ihr eigenes
    # Zeitlimit, weil genau dieser Fall die Schranke noch nicht hatte, und liess
    # dabei die Mutation in der Datei zurück.
    geschrieben = await asyncio.wait_for(
        backfill_embeddings(db_session, provider, batch_size=10, nur_fehlende=False),
        timeout=20,
    )

    assert geschrieben == 3
    # Der alte Vektor war ein Nullvektor; das Mock-Backend liefert einen anderen.
    vektoren = list(await db_session.scalars(select(WorkerNote.embedding)))
    assert all(any(wert != 0.0 for wert in v) for v in vektoren)


@pytest.mark.integration
async def test_alle_neu_terminiert(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    """DER TRAGENDE FALL: Die Schleife muss aufhören.

    Die frühere Fassung blätterte über `embedding IS NULL` — eine Marke, die nur
    solange trägt, wie das Einbetten sie aufhebt. Beim Neu-Einbetten bliebe die
    Auswahl gleich gross, und derselbe Batch käme endlos wieder. Geblättert wird
    deshalb nach Kennung.

    Die kleine Batch-Grösse ist Absicht: Sie erzwingt mehrere Runden, und genau
    dort läge der Fehler.

    MIT ZEITSCHRANKE, und das ist der Punkt: Ohne sie könnte dieser Test eine
    Endlosschleife gar nicht FANGEN — er liefe mit ihr mit und hinge, bis
    irgendwann der ganze Prüflauf abbricht. Ein hängender Lauf sagt nicht, WAS
    kaputt ist. Erst die Schranke macht aus dem Aufhängen ein Testergebnis.
    """
    await _seed_notes(db_session, n_without=0, n_with=5)
    provider = make_provider(
        backends=[make_embed_backend("ollama", dim=1024)], priority="ollama_only"
    )

    geschrieben = await asyncio.wait_for(
        backfill_embeddings(db_session, provider, batch_size=2, nur_fehlende=False),
        timeout=20,
    )

    # Jede Zeile GENAU einmal — nicht mehrfach, wie es eine hängende Schleife
    # täte, und nicht weniger, wie es eine zu grosszügige Blätterung täte.
    assert geschrieben == 5


@pytest.mark.integration
async def test_ohne_alle_neu_bleiben_vorhandene_vektoren_unberuehrt(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    """AUFBAU-KONTROLLE zum Zwangsmodus: Die Vorgabe darf nicht alles anfassen.

    Ohne diesen Zwilling liesse sich `nur_fehlende` versehentlich wirkungslos
    machen — und jeder gewöhnliche Nachhol-Lauf bettete den ganzen Bestand neu
    ein. Das wäre bei einem Cloud-Modell nicht nur langsam, sondern teuer.
    """
    await _seed_notes(db_session, n_without=1, n_with=2)
    provider = make_provider(
        backends=[make_embed_backend("ollama", dim=1024)], priority="ollama_only"
    )

    geschrieben = await backfill_embeddings(db_session, provider, batch_size=10)

    assert geschrieben == 1


@pytest.mark.integration
async def test_die_blaetterung_ueberspringt_keine_zeile(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    """Die Kennungs-Blätterung muss jede Zeile erwischen, auch über Batchgrenzen.

    Ein Fehler um eins (`id >=` statt `id >`) fiele hier auf: Er verarbeitete die
    letzte Zeile eines Batches doppelt und die Schleife käme nie zum Ende.
    """
    await _seed_notes(db_session, n_without=7)
    provider = make_provider(
        backends=[make_embed_backend("ollama", dim=1024)], priority="ollama_only"
    )

    geschrieben = await backfill_embeddings(db_session, provider, batch_size=3)

    assert geschrieben == 7
    assert await _null_count(db_session) == 0
