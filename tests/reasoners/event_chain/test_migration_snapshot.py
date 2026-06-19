# ============================================================
#  FOREMAN — tests/reasoners/event_chain/test_migration_snapshot.py
#  Zweck: Migration 0009 (chain_snapshot/siblings_snapshot) up/down getestet —
#         gegen eine EIGENE ephemere DB, damit die geteilte Test-DB unberührt
#         bleibt. Beweist: upgrade legt die Spalten an, downgrade entfernt sie,
#         erneutes upgrade ist idempotent (sauberer Round-Trip).
#  Hinweis: sync Test (wie die Alembic-Nutzung in conftest) — Alembic führt die
#         async-Engine selbst über asyncio.run; daher KEINE Verschachtelung in
#         einen laufenden Event-Loop.
# ============================================================
from __future__ import annotations

import asyncio

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from foreman.config import Settings

_MIGR_DB = "foreman_test_migr_0009"
_TABLE = "reasoner_explanations"
_SNAPSHOT_COLUMNS = {"chain_snapshot", "siblings_snapshot"}


def _sync_dsn(url: str) -> str:
    """asyncpg-DSN aus der SQLAlchemy-URL (ohne +asyncpg)."""
    return url.replace("+asyncpg", "")


def _swap_db(url: str, db_name: str) -> str:
    """Ersetzt den Datenbanknamen am Ende der URL."""
    return url.rsplit("/", 1)[0] + "/" + db_name


def _reachable(dsn: str) -> bool:
    async def _probe() -> None:
        conn = await asyncpg.connect(dsn, timeout=3)
        await conn.close()

    try:
        asyncio.run(_probe())
        return True
    except Exception:
        return False


def _columns(url: str, table: str) -> set[str]:
    dsn = _sync_dsn(url)

    async def _query() -> set[str]:
        conn = await asyncpg.connect(dsn, timeout=5)
        try:
            rows = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
                table,
            )
            return {row["column_name"] for row in rows}
        finally:
            await conn.close()

    return asyncio.run(_query())


def _admin_exec(admin_dsn: str, statement: str) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(admin_dsn, timeout=5)
        try:
            await conn.execute(statement)
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.mark.integration
def test_migration_0009_up_down_round_trip(test_settings: Settings) -> None:
    base_url = test_settings.database_url
    admin_dsn = _swap_db(_sync_dsn(base_url), "postgres")
    if not _reachable(admin_dsn):
        pytest.skip("Keine Test-DB erreichbar (Migrationstest übersprungen)")

    migr_url = _swap_db(base_url, _MIGR_DB)
    _admin_exec(admin_dsn, f'DROP DATABASE IF EXISTS "{_MIGR_DB}"')
    _admin_exec(admin_dsn, f'CREATE DATABASE "{_MIGR_DB}"')
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", migr_url)
    try:
        # upgrade head → Snapshot-Spalten vorhanden.
        command.upgrade(cfg, "head")
        after_up = _columns(migr_url, _TABLE)
        assert _SNAPSHOT_COLUMNS <= after_up, after_up

        # downgrade auf 0008 → Snapshot-Spalten entfernt, Tabelle bleibt.
        command.downgrade(cfg, "0008")
        after_down = _columns(migr_url, _TABLE)
        assert _SNAPSHOT_COLUMNS.isdisjoint(after_down), after_down
        assert "narrative" in after_down  # die Tabelle selbst existiert weiter

        # erneut upgrade → idempotenter Round-Trip.
        command.upgrade(cfg, "head")
        assert _SNAPSHOT_COLUMNS <= _columns(migr_url, _TABLE)
    finally:
        _admin_exec(admin_dsn, f'DROP DATABASE IF EXISTS "{_MIGR_DB}"')
