# ============================================================
#  FOREMAN — migrations/env.py
#  Zweck: Alembic-Umgebung (async). Liest die DB-URL aus der Config (.env),
#         damit kein Secret im Repo liegt (Repo ist öffentlich).
#  Architektur-Einordnung: DB-Schicht (Schicht 2).
# ============================================================
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from foreman.config import get_settings
from foreman.db import models  # noqa: F401 — registriert alle Tabellen am Metadata
from foreman.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    # Vorrang: explizit gesetzte sqlalchemy.url (z. B. Tests) — sonst Config/.env.
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
