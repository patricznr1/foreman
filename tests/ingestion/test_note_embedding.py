# ============================================================
#  FOREMAN — tests/ingestion/test_note_embedding.py
#  Zweck: Embedding beim Insert (F-SEM, Baustein 5) — best-effort an BEIDEN
#         Schreibpfaden: Ingestion-Service (Batch-Embedding vor Commit) und
#         CRUD-POST. Provider-Ausfall → embedding=NULL, Notiz wird TROTZDEM
#         geschrieben (der Schreibpfad blockiert nie). Provider gemockt (kein Ollama).
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

import asyncpg
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.scenario import load_scenario_by_name
from foreman.api.deps import get_embedding_provider
from foreman.core.pseudonymize import Pseudonymizer
from foreman.core.redact import Redactor
from foreman.embeddings.errors import ProviderUnavailable
from foreman.ingestion.service import IngestionService

pytestmark = pytest.mark.integration


class _CountingProvider:
    """Liefert je Text einen 1024-dim-Vektor und zählt die Batch-Aufrufe."""

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        return [[float(i % 7) for i in range(1024)] for _ in texts]


class _FailProvider:
    """Simuliert ein nicht erreichbares Embedding-Backend."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise ProviderUnavailable("❌ kein Backend (Test)", attempted=("ollama",))


# ----------------------------------------------------------------
#  Ingestion-Schreibpfad (Batch, best-effort)
# ----------------------------------------------------------------
async def test_ingest_embeddet_notizen_in_einem_batch(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    provider = _CountingProvider()
    stats = await IngestionService(
        db_session,
        pseudonymizer=pseudonymizer,
        redactor=fake_redactor,
        embedding_provider=provider,
    ).ingest(adapter)

    assert stats.worker_notes == 2
    assert stats.notes_embedded == 2
    # Batch-Garantie: EIN embed-Call für beide Notizen, nicht pro Notiz.
    assert provider.calls == 1
    missing = await raw_conn.fetchval("SELECT count(*) FROM worker_notes WHERE embedding IS NULL")
    assert missing == 0


async def test_ingest_provider_ausfall_schreibt_notiz_mit_null_embedding(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    stats = await IngestionService(
        db_session,
        pseudonymizer=pseudonymizer,
        redactor=fake_redactor,
        embedding_provider=_FailProvider(),
    ).ingest(adapter)

    # Notizen wurden geschrieben (best-effort) — nur ohne Embedding.
    assert stats.worker_notes == 2
    assert stats.notes_embedded == 0
    written = await raw_conn.fetchval("SELECT count(*) FROM worker_notes")
    null_embeddings = await raw_conn.fetchval(
        "SELECT count(*) FROM worker_notes WHERE embedding IS NULL"
    )
    assert written == 2
    assert null_embeddings == 2


async def test_ingest_ohne_provider_laesst_embedding_null(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    stats = await IngestionService(
        db_session, pseudonymizer=pseudonymizer, redactor=fake_redactor
    ).ingest(adapter)  # embedding_provider=None (Default)

    assert stats.worker_notes == 2
    assert stats.notes_embedded == 0
    null_embeddings = await raw_conn.fetchval(
        "SELECT count(*) FROM worker_notes WHERE embedding IS NULL"
    )
    assert null_embeddings == 2


# ----------------------------------------------------------------
#  CRUD-POST-Schreibpfad (Einzel, best-effort)
# ----------------------------------------------------------------
async def test_crud_post_embeddet_notiz(
    auth_client: AsyncClient, raw_conn: asyncpg.Connection
) -> None:
    # Default-Stub-Provider (aus der app-Fixture) bettet ein → embedding gesetzt.
    resp = await auth_client.post(
        "/api/v1/worker_notes", json={"text": "Lager läuft heiß", "shift": "frueh"}
    )
    assert resp.status_code == 201, resp.text
    note_id = resp.json()["id"]
    has_embedding = await raw_conn.fetchval(
        "SELECT embedding IS NOT NULL FROM worker_notes WHERE id = $1", note_id
    )
    assert has_embedding is True


async def test_crud_post_provider_ausfall_schreibt_notiz_mit_null_embedding(
    app: FastAPI, auth_client: AsyncClient, raw_conn: asyncpg.Connection
) -> None:
    app.dependency_overrides[get_embedding_provider] = lambda: _FailProvider()
    resp = await auth_client.post(
        "/api/v1/worker_notes", json={"text": "Lager läuft heiß", "shift": "frueh"}
    )
    # Notiz wurde geschrieben (best-effort) — nur ohne Embedding.
    assert resp.status_code == 201, resp.text
    note_id = resp.json()["id"]
    has_embedding = await raw_conn.fetchval(
        "SELECT embedding IS NOT NULL FROM worker_notes WHERE id = $1", note_id
    )
    assert has_embedding is False
