# ============================================================
#  FOREMAN — tests/conftest.py
#  Zweck: gemeinsame Test-Fixtures — Test-App, Test-DB (Migrationen), Auth-Helper,
#         Stub-Redactor (kein 560-MB-spaCy-Modell in der Suite).
#  Architektur-Einordnung: Test-Infrastruktur (Quality Gates §10.3).
#  Integrationstests laufen gegen eine echte (Timescale-)DB; ist keine erreichbar,
#  werden sie sauber übersprungen (Muster: „DB-Tests skippen sonst").
# ============================================================
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.api.deps import get_embedding_provider, get_redactor
from foreman.config import Settings, get_settings
from foreman.core.pseudonymize import Pseudonymizer, build_pseudonymizer
from foreman.db.session import get_session
from foreman.main import create_app

# Test-Schlüssel für die HMAC-Pseudonymisierung (32-Byte-Hex). Nur für Tests.
os.environ.setdefault("FOREMAN_PSEUDO_KEY_v1", "11" * 32)

TEST_DATABASE_URL = os.environ.get(
    "FOREMAN_TEST_DATABASE_URL",
    "postgresql+asyncpg://foreman:foreman@localhost:5433/foreman_test",
)

# Reihenfolge egal — CASCADE/RESTART IDENTITY räumt alles ab.
_TRUNCATE_SQL = text(
    "TRUNCATE readings, worker_notes, maintenance_events, production_runs, "
    "alarms, data_points, components, semantic_events, machines, audit_logs, "
    "lines, users RESTART IDENTITY CASCADE;"
)


def _db_reachable(database_url: str) -> bool:
    dsn = database_url.replace("+asyncpg", "")

    async def _probe() -> None:
        conn = await asyncpg.connect(dsn, timeout=3)
        await conn.close()

    try:
        asyncio.run(_probe())
        return True
    except Exception:
        return False


class FakeRedactor:
    """Test-Doppel für den NER-Redactor (kein spaCy-Modell nötig).

    Maskiert eine bekannte Namensliste deterministisch — prüft die Verdrahtung
    des Schreibpfads, nicht die NER-Qualität (die deckt ein Unit-Test mit Mock ab).
    """

    _NAMES = ("Schmidt", "Müller", "Meier", "Weber", "Nowak")

    def redact_person_names(self, text_value: str) -> str:
        for name in self._NAMES:
            text_value = text_value.replace(name, "[PERSON]")
        return text_value


class _StubEmbeddingProvider:
    """Schneller Embedding-Stub für die Test-App (kein echtes Ollama).

    Liefert einen deterministischen Nullvektor je Text — der CRUD-Schreibpfad
    läuft so ohne Netz/Timeout durch. Tests, die echte Such-Reihenfolge oder den
    Backend-Ausfall prüfen, überschreiben den Provider gezielt selbst."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1024 for _ in texts]


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Konfiguration für Tests: Test-DB, fixer JWT-Secret, v1-Pseudo-Schlüssel, kein Substrat."""
    return Settings(
        _env_file=None,  # nicht die echte .env lesen
        database_url=TEST_DATABASE_URL,
        jwt_secret="test-secret-foreman-f2-0123456789abcdef",  # ≥32 Byte (HS256)
        jwt_expire_minutes=60,
        pseudo_key_version="v1",
        pseudo_key_versions="v1",
        pseudo_tenant="default",
        substrate_base_url=None,
        log_level="WARNING",
    )


@pytest.fixture(scope="session")
def _migrated_db(test_settings: Settings) -> Iterator[None]:
    """Wendet die Migrationen auf die Test-DB an (oder überspringt, wenn keine DB da)."""
    if not _db_reachable(test_settings.database_url):
        pytest.skip("Keine Test-DB erreichbar (Integrationstest übersprungen)")
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_settings.database_url)
    command.upgrade(cfg, "head")
    yield
    # Teardown: kompletter Reset (Container ist ohnehin ephemer).
    dsn = test_settings.database_url.replace("+asyncpg", "")

    async def _reset() -> None:
        conn = await asyncpg.connect(dsn, timeout=5)
        try:
            await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        finally:
            await conn.close()

    asyncio.run(_reset())


@pytest_asyncio.fixture
async def app(test_settings: Settings, _migrated_db: None) -> AsyncIterator[FastAPI]:
    """Test-App mit Test-DB-Session + Stub-Redactor. Tests können weitere
    Dependency-Overrides ergänzen (z. B. get_substrate_client)."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    # Isolation: vor jedem Test leeren.
    async with engine.begin() as conn:
        await conn.execute(_TRUNCATE_SQL)

    application = create_app(test_settings)

    async def _override_get_session() -> AsyncIterator[object]:
        async with maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    application.dependency_overrides[get_session] = _override_get_session
    application.dependency_overrides[get_settings] = lambda: test_settings
    application.dependency_overrides[get_redactor] = lambda: FakeRedactor()
    application.dependency_overrides[get_embedding_provider] = lambda: _StubEmbeddingProvider()

    yield application

    await engine.dispose()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async-Test-Client gegen die Test-App."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


@pytest_asyncio.fixture
async def raw_conn(_migrated_db: None) -> AsyncIterator[asyncpg.Connection]:
    """Direkte asyncpg-Verbindung zur Test-DB für Persistenz-Checks (z. B. Hypertable)."""
    dsn = TEST_DATABASE_URL.replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn, timeout=5)
    try:
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def clean_db(test_settings: Settings, _migrated_db: None) -> AsyncIterator[None]:
    """Leert die Test-DB vor dem Test (für direkte Service-/Ingestion-Tests)."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(_TRUNCATE_SQL)
    await engine.dispose()
    yield


@pytest_asyncio.fixture
async def db_session(
    test_settings: Settings, clean_db: None
) -> AsyncIterator[object]:
    """Eine AsyncSession gegen die (geleerte) Test-DB — für IngestionService-Tests."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def pseudonymizer(test_settings: Settings) -> Pseudonymizer:
    """Pseudonymizer aus den Test-Schlüsseln (HMAC, §8)."""
    return build_pseudonymizer(test_settings)


@pytest.fixture
def fake_redactor() -> FakeRedactor:
    """NER-Stub (maskiert bekannte Namen) — kein 560-MB-spaCy-Modell in der Suite."""
    return FakeRedactor()


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient) -> str:
    """Registriert einen Test-Nutzer und gibt ein gültiges JWT zurück."""
    creds = {"email": "tester@foreman.de", "password": "supersecret1"}
    await client.post("/auth/register", json=creds)
    response = await client.post("/auth/login", json=creds)
    token: str = response.json()["access_token"]
    return token


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, auth_token: str) -> AsyncClient:
    """Client mit gesetztem Bearer-Token für geschützte Routen."""
    client.headers["Authorization"] = f"Bearer {auth_token}"
    return client
