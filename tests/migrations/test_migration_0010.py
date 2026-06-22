# ============================================================
#  FOREMAN — tests/migrations/test_migration_0010.py
#  Zweck: Migration 0010 (Audit-Trail/Topologie-Quelle, Sektion I) als echter
#         up/down-Round-Trip plus Nachweis der DB-seitigen Unveränderlichkeit:
#         INSERT erlaubt, UPDATE/DELETE vom Append-Only-Trigger abgewiesen.
#  Architektur-Einordnung: Test-Infrastruktur (Quality Gates §10.3).
#  Muster (D-Lehre): eigene ephemere DB je Lauf (eindeutiger Name via uuid4 →
#         keine Parallelitäts-Kollision); SYNC-Test (Alembic fährt eigene
#         async-Engine über asyncio.run, darf nicht in einer laufenden Loop nisten).
# ============================================================
from __future__ import annotations

import asyncio
from uuid import uuid4

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from foreman.config import Settings

pytestmark = pytest.mark.integration

_MIGR_DB = "foreman_test_migr_0010"
_TABLE = "audit_logs"
# Die additiv ergänzten Spalten (0010).
_NEW_COLUMNS = {
    "actor",
    "actor_role",
    "action_type",
    "target_kind",
    "target_id",
    "machine_id",
    "origin",
    "detail",
    "occurred_at",
}


def _sync_dsn(url: str) -> str:
    """asyncpg-DSN aus der SQLAlchemy-URL (ohne +asyncpg)."""
    return url.replace("+asyncpg", "")


def _swap_db(url: str, db_name: str) -> str:
    """Ersetzt den Datenbanknamen am Ende der URL."""
    return url.rsplit("/", 1)[0] + "/" + db_name


def _reachable(admin_dsn: str) -> bool:
    async def _probe() -> None:
        conn = await asyncpg.connect(admin_dsn, timeout=3)
        await conn.close()

    try:
        asyncio.run(_probe())
        return True
    except Exception:
        return False


def _admin_exec(dsn: str, statement: str) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(dsn, timeout=5)
        try:
            await conn.execute(statement)
        finally:
            await conn.close()

    asyncio.run(_run())


def _fetchval(dsn: str, statement: str) -> object:
    async def _run() -> object:
        conn = await asyncpg.connect(dsn, timeout=5)
        try:
            return await conn.fetchval(statement)
        finally:
            await conn.close()

    return asyncio.run(_run())


def _columns(dsn: str, table: str) -> set[str]:
    async def _run() -> set[str]:
        conn = await asyncpg.connect(dsn, timeout=5)
        try:
            rows = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
                table,
            )
            return {row["column_name"] for row in rows}
        finally:
            await conn.close()

    return asyncio.run(_run())


def test_migration_0010_up_down_round_trip_and_immutability(test_settings: Settings) -> None:
    base_url = test_settings.database_url
    admin_dsn = _swap_db(_sync_dsn(base_url), "postgres")
    if not _reachable(admin_dsn):
        pytest.skip("Keine Test-DB erreichbar (Migrationstest übersprungen)")

    migr_db = f"{_MIGR_DB}_{uuid4().hex[:8]}"
    migr_url = _swap_db(base_url, migr_db)
    sync_url = _sync_dsn(migr_url)
    _admin_exec(admin_dsn, f'DROP DATABASE IF EXISTS "{migr_db}"')
    _admin_exec(admin_dsn, f'CREATE DATABASE "{migr_db}"')
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", migr_url)
    try:
        # upgrade head → die neuen Spalten existieren.
        command.upgrade(cfg, "head")
        cols = _columns(sync_url, _TABLE)
        assert _NEW_COLUMNS <= cols, cols

        # INSERT bleibt erlaubt (append-only ≠ insert-verboten).
        new_id = _fetchval(
            sync_url,
            "INSERT INTO audit_logs (action, action_type, origin) "
            "VALUES ('mcp_retrieval', 'mcp_retrieval', 'mcp') RETURNING id",
        )
        assert new_id is not None

        # UPDATE wird vom Trigger abgewiesen.
        with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
            _admin_exec(sync_url, f"UPDATE audit_logs SET action = 'x' WHERE id = {new_id}")

        # DELETE wird vom Trigger abgewiesen.
        with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
            _admin_exec(sync_url, f"DELETE FROM audit_logs WHERE id = {new_id}")

        # Die CHECK-Constraints weisen Fremdwerte ab (Defense-in-Depth).
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            _admin_exec(
                sync_url,
                "INSERT INTO audit_logs (action, action_type) VALUES ('x', 'not_a_type')",
            )

        # downgrade auf 0009 → Spalten + Trigger weg, Tabelle + Legacy-Spalten bleiben.
        command.downgrade(cfg, "0009")
        cols_after = _columns(sync_url, _TABLE)
        assert _NEW_COLUMNS.isdisjoint(cols_after), cols_after
        assert "action" in cols_after  # die Tabelle selbst überlebt
        # Ohne Trigger sind UPDATE/DELETE wieder möglich (sauber zurückgebaut).
        legacy_id = _fetchval(
            sync_url, "INSERT INTO audit_logs (action) VALUES ('legacy') RETURNING id"
        )
        _admin_exec(sync_url, f"UPDATE audit_logs SET action = 'y' WHERE id = {legacy_id}")
        _admin_exec(sync_url, f"DELETE FROM audit_logs WHERE id = {legacy_id}")

        # erneut upgrade → idempotenter Round-Trip.
        command.upgrade(cfg, "head")
        assert _NEW_COLUMNS <= _columns(sync_url, _TABLE)
    finally:
        _admin_exec(admin_dsn, f'DROP DATABASE IF EXISTS "{migr_db}"')
