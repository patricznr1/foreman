# ============================================================
#  FOREMAN — db/session.py
#  Zweck: Async-Engine, Session-Factory, FastAPI-Session-Dependency, Pool.
#  Architektur-Einordnung: Persistenz-Schicht (Schicht 2). Connection-Pooling
#         nach docs/research/timescaledb-tuning-readings.md §3.4 (kein
#         Verbindungs-Overhead pro Batch).
# ============================================================
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from foreman.config import Settings, get_settings

# Modul-weite, bewusst dokumentierte Singletons (lazy initialisiert),
# damit Engine + Pool über die App-Lebensdauer wiederverwendet werden.
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings | None = None) -> AsyncEngine:
    """Initialisiert Engine + Session-Factory (idempotent)."""
    global _engine, _sessionmaker
    if _engine is None:
        cfg = settings or get_settings()
        _engine = create_async_engine(
            cfg.database_url,
            echo=cfg.db_echo,
            pool_size=cfg.db_pool_size,
            max_overflow=cfg.db_max_overflow,
            pool_pre_ping=True,
        )
        _sessionmaker = async_sessionmaker(
            bind=_engine, expire_on_commit=False, autoflush=False
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Liefert die Session-Factory (initialisiert die Engine bei Bedarf)."""
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    """Gibt den Pool frei (App-Shutdown / Test-Teardown)."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-Dependency: liefert eine Session pro Request, committed/rollbackt sauber."""
    maker = get_sessionmaker()
    async with maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
