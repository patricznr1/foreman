# ============================================================
#  FOREMAN — tests/migrations/test_migration_0011.py
#  Zweck: Migration 0011 (drift_profiles — persistiertes F4-Eigenprofil) als
#         echter up/down-Round-Trip plus Nachweis der Defense-in-Depth-CHECKs:
#         ein Profil ohne etablierte Streuung (noise_sigma <= 0) bzw. ohne
#         positiven Schwellenfaktor (effect_size_k <= 0) wird DB-seitig abgewiesen
#         (kein geratenes Band), und je data_point existiert höchstens ein Profil
#         (Upsert-Ziel über die Unique-Constraint).
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

_MIGR_DB = "foreman_test_migr_0011"
_TABLE = "drift_profiles"
# Die in 0011 angelegten Spalten.
_NEW_COLUMNS = {
    "id",
    "data_point_id",
    "machine_id",
    "state_medians",
    "noise_sigma",
    "effect_size_k",
    "window_samples",
    "warmup_samples",
    "total_samples",
    "computed_at",
    "created_at",
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


def _seed_data_point(dsn: str) -> tuple[int, int]:
    """Legt Linie/Maschine/Datenpunkt an (FK-Ziele) und gibt (machine_id, data_point_id)."""

    async def _run() -> tuple[int, int]:
        conn = await asyncpg.connect(dsn, timeout=5)
        try:
            machine_id = await conn.fetchval(
                "INSERT INTO machines (label) VALUES ('M') RETURNING id"
            )
            data_point_id = await conn.fetchval(
                "INSERT INTO data_points (machine_id, name, kind) "
                "VALUES ($1, 'vibration', 'analog') RETURNING id",
                machine_id,
            )
            return int(machine_id), int(data_point_id)
        finally:
            await conn.close()

    return asyncio.run(_run())


def _insert_profile(
    dsn: str, data_point_id: int, machine_id: int, *, sigma: float, k: float
) -> int:
    async def _run() -> int:
        conn = await asyncpg.connect(dsn, timeout=5)
        try:
            new_id: int = await conn.fetchval(
                "INSERT INTO drift_profiles "
                "(data_point_id, machine_id, state_medians, noise_sigma, effect_size_k, "
                " window_samples, warmup_samples, total_samples, computed_at) "
                "VALUES ($1, $2, '{}'::jsonb, $3, $4, 1440, 100, 200, now()) RETURNING id",
                data_point_id,
                machine_id,
                sigma,
                k,
            )
            return int(new_id)
        finally:
            await conn.close()

    return asyncio.run(_run())


def test_migration_0011_up_down_round_trip_and_checks(test_settings: Settings) -> None:
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
        # upgrade head → die Tabelle + Spalten existieren.
        command.upgrade(cfg, "head")
        cols = _columns(sync_url, _TABLE)
        assert _NEW_COLUMNS <= cols, cols

        machine_id, data_point_id = _seed_data_point(sync_url)

        # Ein gültiges Profil (etablierte Streuung, positiver Faktor) wird angenommen.
        profile_id = _insert_profile(sync_url, data_point_id, machine_id, sigma=0.42, k=3.0)
        assert profile_id is not None

        # CHECK noise_sigma > 0: ein Profil ohne etablierte Streuung wird abgewiesen
        # (kein geratenes Band — Ehrlichkeitslinie auch an der Persistenzgrenze).
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            _insert_profile(sync_url, data_point_id, machine_id, sigma=0.0, k=3.0)

        # CHECK effect_size_k > 0: ein nicht-positiver Schwellenfaktor wird abgewiesen.
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            _insert_profile(sync_url, data_point_id, machine_id, sigma=0.42, k=0.0)

        # Unique data_point_id: höchstens ein Profil je Datenpunkt (Upsert-Ziel).
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            _insert_profile(sync_url, data_point_id, machine_id, sigma=0.5, k=3.0)

        # downgrade auf 0010 → Tabelle weg.
        command.downgrade(cfg, "0010")
        assert _TABLE not in _columns_tables(sync_url)

        # erneut upgrade → idempotenter Round-Trip.
        command.upgrade(cfg, "head")
        assert _NEW_COLUMNS <= _columns(sync_url, _TABLE)
    finally:
        _admin_exec(admin_dsn, f'DROP DATABASE IF EXISTS "{migr_db}"')


def _columns_tables(dsn: str) -> set[str]:
    """Alle Tabellennamen im public-Schema (für den Drop-Nachweis nach downgrade)."""

    async def _run() -> set[str]:
        conn = await asyncpg.connect(dsn, timeout=5)
        try:
            rows = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
            return {row["table_name"] for row in rows}
        finally:
            await conn.close()

    return asyncio.run(_run())
