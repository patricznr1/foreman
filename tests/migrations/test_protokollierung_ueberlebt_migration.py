# ============================================================
#  FOREMAN — tests/migrations/test_protokollierung_ueberlebt_migration.py
#  Zweck: Ein Migrationslauf im selben Prozess darf die Protokollierung der
#         Anwendung nicht abschalten.
#  Architektur-Einordnung: Test-Infrastruktur (Quality Gates §10.3).
#  Hintergrund: `migrations/env.py` richtet die Protokollierung über
#         `logging.config.fileConfig` ein. Deren Standardwert
#         `disable_existing_loggers=True` schaltet JEDEN bereits erzeugten Logger
#         stumm — also alle FOREMAN-Logger, die beim Import ihres Moduls
#         entstanden sind. Der Ausfall ist lautlos: kein Fehler, keine Meldung,
#         nur Stille. Und mit ihm fällt jede Prüfung aus, die Protokollzeilen
#         betrachtet — sie liest dann eine leere Ausgabe und besteht.
#  Muster: SYNC-Test wie die übrigen Migrations-Tests (Alembic fährt eine eigene
#         async-Engine über asyncio.run und darf nicht in einer laufenden Loop
#         nisten); eigene ephemere Datenbank je Lauf.
# ============================================================
from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from foreman.config import Settings

pytestmark = pytest.mark.integration

ZEUGE = "foreman.zeuge.migrationslauf"


def _tausche_db(url: str, name: str) -> str:
    """Ersetzt den Datenbanknamen am Ende der URL (Muster der übrigen Migrations-Tests)."""
    return url.rsplit("/", 1)[0] + "/" + name


def _erreichbar(verwaltungs_dsn: str) -> bool:
    async def _anklopfen() -> None:
        conn = await asyncpg.connect(verwaltungs_dsn, timeout=3)
        await conn.close()

    try:
        asyncio.run(_anklopfen())
        return True
    except Exception:
        return False


def test_die_protokollierung_der_anwendung_ueberlebt_den_migrationslauf(
    test_settings: Settings,
) -> None:
    """Ein vor der Migration erzeugter Logger ist danach weiterhin hörbar.

    Geprüft wird der Zustand NACH einem echten `alembic upgrade head` — nicht der
    Quelltext von `env.py`. Eine Textsuche fände die Einstellung auch im Kommentar,
    der sie erklärt, und wäre gegen eine spätere Umstellung blind.
    """
    zeuge = logging.getLogger(ZEUGE)
    zeuge.disabled = False
    assert not zeuge.disabled, "Aufbau: Der Zeuge muss vor dem Lauf hörbar sein."

    basis = test_settings.database_url
    verwaltung = _tausche_db(basis.replace("+asyncpg", ""), "postgres")
    if not _erreichbar(verwaltung):
        pytest.skip("Keine Test-DB erreichbar (Migrationstest übersprungen)")

    name = f"foreman_migr_log_{uuid4().hex[:8]}"

    async def _anlegen() -> None:
        conn = await asyncpg.connect(verwaltung, timeout=5)
        try:
            await conn.execute(f'CREATE DATABASE "{name}"')
        finally:
            await conn.close()

    async def _verwerfen() -> None:
        conn = await asyncpg.connect(verwaltung, timeout=5)
        try:
            await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        finally:
            await conn.close()

    asyncio.run(_anlegen())
    try:
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", _tausche_db(basis, name))
        command.upgrade(cfg, "head")

        assert not zeuge.disabled, (
            "❌ Der Migrationslauf hat bestehende Logger abgeschaltet. `fileConfig` in "
            "migrations/env.py braucht `disable_existing_loggers=False` — sonst "
            "verstummt die Protokollierung der Anwendung lautlos, und jede Prüfung, "
            "die Protokollzeilen liest, besteht auf einer leeren Ausgabe."
        )
    finally:
        asyncio.run(_verwerfen())
