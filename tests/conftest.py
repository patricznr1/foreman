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
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

import asyncpg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from foreman.api.deps import get_embedding_provider, get_redactor
from foreman.config import Settings, get_settings
from foreman.core.pseudonymize import Pseudonymizer, build_pseudonymizer
from foreman.core.roles import Role
from foreman.db.models import User
from foreman.db.provisioning import create_user
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

# Nur readings_1m wird in der Suite gelesen (load_readings/latest_values); die 1h/1d-
# Aggregate liest kein Code-Pfad → kein Reset nötig (spart den Refresh-Overhead).
_RESET_CAGGS = ("readings_1m",)


# Wie oft ein Refresh bei einem Sperrkonflikt wiederholt wird, und wie lange
# dazwischen gewartet wird. Beides klein gehalten: Der Konflikt löst sich, sobald
# der fremde Lauf fertig ist — das dauert Millisekunden, nicht Sekunden.
_CAGG_VERSUCHE = 5
_CAGG_WARTEZEIT_S = 0.2


async def _refresh_mit_wiederholung(conn: AsyncConnection, cagg: str) -> None:
    """Refresht ein Aggregat und wiederholt bei einem Sperrkonflikt.

    ANLASS (zweimal am 25.08.2026, einmal örtlich, einmal in der CI):
    TimescaleDB betreibt einen eigenen Hintergrund-Scheduler, der dieselben
    Aggregate materialisiert. Trifft er mit diesem Refresh zusammen, bricht der
    Aufruf mit einem Sperrkonflikt ab — und weil er in einer Fixture steckt,
    scheitert der Test schon beim AUFBAU. Getroffen wird dabei irgendein Test,
    nicht der schuldige: Beide Male fiel es auf einen Archiv-Routentest, der mit
    Aggregaten nichts zu tun hat.

    EIN SPERRKONFLIKT IST EIN WEGFEHLER, kein Befund über die Daten: Der fremde
    Lauf ist in Millisekunden fertig, danach gelingt derselbe Aufruf. Deshalb
    wiederholen statt scheitern.

    NICHT VERSCHLUCKT: Nach `_CAGG_VERSUCHE` Anläufen fliegt die Ausnahme weiter.
    Ein still übersprungener Reset hinterliesse materialisierte Buckets, und die
    tauchen später als Geister-Werte eines fremden Datenpunkts auf — ein Fehler,
    der weit schwerer zu finden wäre als ein roter Aufbau.
    """
    for versuch in range(1, _CAGG_VERSUCHE + 1):
        try:
            # ORM-Ausnahme: `refresh_continuous_aggregate` ist eine Prozedur von
            # TimescaleDB, keine Tabelle — das ORM hat dafür keine Entsprechung.
            await conn.execute(
                text(
                    f"CALL refresh_continuous_aggregate('{cagg}'::regclass, "
                    "NULL::timestamptz, NULL::timestamptz)"
                )
            )
            return
        except DBAPIError as fehler:
            # 55P03 = lock_not_available. Jede andere Ursache ist kein Wettlauf
            # und darf NICHT wiederholt werden — sie wiederholte sich nur, ohne
            # besser zu werden.
            if getattr(fehler.orig, "sqlstate", None) != "55P03":
                raise
            if versuch == _CAGG_VERSUCHE:
                raise
            await asyncio.sleep(_CAGG_WARTEZEIT_S)


@pytest.fixture
def cagg_refresh() -> tuple[Callable[..., Awaitable[None]], int]:
    """Reicht die Refresh-Wiederholung samt Versuchszahl an einen Test weiter.

    Warum als Fixture statt als Import: `tests` ist kein Paket, und ein
    `from tests.conftest import …` trägt nur dort, wo das Arbeitsverzeichnis
    zufällig im Suchpfad liegt — örtlich ja, im Prüflauf nicht. Über eine Fixture
    findet pytest die Funktion auf seinem eigenen Weg, ohne dass die
    Verzeichnisstruktur dafür umgebaut werden müsste.
    """
    return _refresh_mit_wiederholung, _CAGG_VERSUCHE


async def _reset_caggs(engine: AsyncEngine) -> None:
    """Räumt die materialisierten CAGG-Buckets nach dem TRUNCATE ab (Test-Isolation).

    TRUNCATE der `readings`-Quelle invalidiert die Continuous Aggregates NICHT —
    materialisierte Buckets bleiben stehen und tauchen bei data_point_id-Wieder-
    verwendung (RESTART IDENTITY) als „Geister-Werte" eines fremden Datenpunkts auf
    (z. B. ein latest_value-Read über readings_1m ohne Zeitfenster). Ein Refresh über
    die nun leere Quelle entfernt die materialisierten Buckets. `refresh_continuous_
    aggregate` darf NICHT in einer Transaktion laufen → AUTOCOMMIT.
    """
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        for cagg in _RESET_CAGGS:
            await _refresh_mit_wiederholung(conn, cagg)


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
    await _reset_caggs(engine)

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
    await _reset_caggs(engine)
    await engine.dispose()
    yield


@pytest_asyncio.fixture
async def db_session(test_settings: Settings, clean_db: None) -> AsyncIterator[object]:
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


# Einheitliches Test-Passwort (erfüllt PASSWORD_MIN aus schemas/auth.py).
TEST_PASSWORD = "supersecret1"


async def ensure_user(test_settings: Settings, email: str, role: Role) -> None:
    """Legt einen Test-Nutzer über den PRODUKTIONS-Anlagepfad an (idempotent).

    Die Suite nutzt denselben Weg wie der Betrieb (§4/§19) — über HTTP wird keine
    Rolle vergeben, auch nicht im Test. Idempotent, weil mehrere Tests
    derselben Datei denselben Nutzer anfordern und nicht zwischen jedem Test
    getruncatet wird — `create_user` selbst bleibt bewusst strikt (kein
    Überschreiben). Dieselbe E-Mail mit ABWEICHENDER Rolle ist ein Testfehler und
    knallt hier, statt still die falsche Rolle zu verwenden.
    """
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            existing = await session.scalar(select(User).where(User.email == email))
            if existing is not None:
                assert existing.role == role.value, (
                    f"❌ Test-Nutzer {email} existiert mit Rolle {existing.role}, "
                    f"angefordert war {role.value}"
                )
                return
            await create_user(session, email=email, password=TEST_PASSWORD, role=role)
            await session.commit()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient, test_settings: Settings) -> str:
    """Legt einen Test-Nutzer (Rolle `shift_lead`) an und gibt ein gültiges JWT
    zurück. shift_lead ist der operative Standard-Nutzer der Suite — er darf die
    Trigger-/Quittier-Routen (§21.18), damit die bestehenden Reasoner-Tests den
    Erfolgs-Pfad prüfen; rollenspezifische Sperren testet `auth_headers_for`."""
    email = "tester@foreman.de"
    await ensure_user(test_settings, email, Role.SHIFT_LEAD)
    response = await client.post("/auth/login", json={"email": email, "password": TEST_PASSWORD})
    token: str = response.json()["access_token"]
    return token


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, auth_token: str) -> AsyncClient:
    """Client mit gesetztem Bearer-Token für geschützte Routen."""
    client.headers["Authorization"] = f"Bearer {auth_token}"
    return client


@pytest_asyncio.fixture
def auth_headers_for(
    client: AsyncClient, test_settings: Settings
) -> Callable[[str, str], Awaitable[dict[str, str]]]:
    """Factory: legt einen Nutzer mit gegebener Rolle an, loggt ihn ein und liefert
    den Bearer-Header — für rollenspezifische RBAC-Tests (§21.18). Mehrere Aufrufe
    mit verschiedenen E-Mails/Rollen sind möglich (jeder eigener Nutzer)."""

    async def _make(email: str, role: str) -> dict[str, str]:
        await ensure_user(test_settings, email, Role(role))
        resp = await client.post("/auth/login", json={"email": email, "password": TEST_PASSWORD})
        token: str = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def ensure_user_sync(test_settings: Settings) -> Callable[[str, str], None]:
    """Sync-Variante von `ensure_user` für die TestClient-basierten WS-Tests.

    Der TestClient fährt seinen Event-Loop in einem eigenen Portal-Thread, im
    Test-Thread läuft keiner — `asyncio.run` ist hier also sicher."""

    def _make(email: str, role: str) -> None:
        asyncio.run(ensure_user(test_settings, email, Role(role)))

    return _make
