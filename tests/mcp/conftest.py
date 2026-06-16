# ============================================================
#  FOREMAN — tests/mcp/conftest.py
#  Zweck: Fixtures der MCP-Schicht (F7). Initialisiert die GLOBALE Engine gegen die
#         Test-DB — genau den Session-Pfad (get_sessionmaker), den die MCP-Tools
#         zur Laufzeit nutzen. So testen die Tool-Wrapper das echte Verhalten.
#  Architektur-Einordnung: Test-Infrastruktur (Quality Gates §10.3).
# ============================================================
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.config import Settings
from foreman.db.session import dispose_engine, get_sessionmaker, init_engine


@pytest_asyncio.fixture
async def mcp_session(test_settings: Settings, clean_db: None) -> AsyncIterator[AsyncSession]:
    """Globale Engine gegen die geleerte Test-DB; liefert eine Session zum Seeden.

    Die Tool-Wrapper holen ihre eigene Session über `get_sessionmaker()` (dieselbe
    globale Factory) — Seed + Commit über diese Fixture-Session sind danach sichtbar.
    """
    await dispose_engine()
    init_engine(test_settings)
    maker = get_sessionmaker()
    async with maker() as session:
        yield session
    await dispose_engine()
