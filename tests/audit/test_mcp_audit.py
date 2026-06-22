# ============================================================
#  FOREMAN — tests/audit/test_mcp_audit.py
#  Zweck: Integrationstest Sektion I (MCP-Audit) — ein MCP-Tool-Aufruf erzeugt
#         genau eine `mcp_retrieval`-Audit-Zeile (pseudonymer Single-Consumer-
#         Actor), UND der Tool-Pfad bleibt nachweislich read-only: der Audit-Sink
#         schreibt auf EIGENER, separat committeter Session (Invariante I intakt).
#  Architektur-Einordnung: Test-Infrastruktur (Quality Gates §10.3).
# ============================================================
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.audit.writer import ACTION_MCP_RETRIEVAL, MCP_ACTOR_ROLE, MCP_CONSUMER_LABEL
from foreman.config import Settings
from foreman.core.pseudonymize import Pseudonymizer
from foreman.db.models import AuditLog, Machine
from foreman.db.session import dispose_engine, get_sessionmaker, init_engine
from foreman.mcp.tools import get_machine, list_machines

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def global_session(test_settings: Settings, clean_db: None) -> AsyncIterator[AsyncSession]:
    """Globale Engine gegen die geleerte Test-DB — genau der Session-Pfad, den die
    MCP-Tools (get_sessionmaker) zur Laufzeit nutzen."""
    await dispose_engine()
    init_engine(test_settings)
    maker = get_sessionmaker()
    async with maker() as session:
        yield session
    await dispose_engine()


async def test_mcp_tool_call_writes_single_mcp_retrieval_row(
    global_session: AsyncSession, pseudonymizer: Pseudonymizer
) -> None:
    machine = Machine(label="M")
    global_session.add(machine)
    await global_session.commit()
    machine_id = machine.id

    out = await get_machine(machine_id)
    assert out.id == machine_id

    maker = get_sessionmaker()
    async with maker() as session:
        rows = list((await session.scalars(select(AuditLog))).all())
    assert len(rows) == 1, rows
    row = rows[0]
    assert row.action_type == ACTION_MCP_RETRIEVAL
    assert row.origin == "mcp"
    assert row.target_kind == "machine"
    assert row.target_id == machine_id
    assert row.machine_id == machine_id
    assert row.actor_role == MCP_ACTOR_ROLE
    assert row.detail == {"tool": "get_machine", "result": "ok"}
    # §8 / Test 6: actor ist das pseudonymisierte Single-Consumer-Label, nie Klartext.
    assert row.actor == pseudonymizer.tokenize_worker(MCP_CONSUMER_LABEL)
    assert MCP_CONSUMER_LABEL not in str(row.actor)
    assert row.user_id is None


async def test_mcp_read_path_stays_read_only_with_separate_audit_commit(
    global_session: AsyncSession,
) -> None:
    machine = Machine(label="M")
    global_session.add(machine)
    await global_session.commit()
    before = await global_session.scalar(select(func.count()).select_from(Machine))

    # Ein reines Lese-Tool: darf KEINE Domänendaten verändern.
    await list_machines()

    maker = get_sessionmaker()
    async with maker() as session:
        after = await session.scalar(select(func.count()).select_from(Machine))
        audit_count = await session.scalar(select(func.count()).select_from(AuditLog))
    # Der Tool-Pfad hat nichts an den Domänendaten geändert (read-only).
    assert after == before
    # Trotzdem ist genau eine Audit-Zeile da → sie kam aus dem SEPARAT committeten
    # Audit-Sink (die read-only Tool-Session committet nie → Invariante I intakt).
    assert audit_count == 1
