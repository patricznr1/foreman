# ============================================================
#  FOREMAN — tests/integration/test_dual_write.py
#  Zweck: Pflicht-Test: Dual-Write spiegelt diskrete Ereignisse in
#  semantic_events; bei erreichbarem Substrat wird substrate_ref gesetzt; ein
#  Substrat-Ausfall blockiert den Readings-/Event-Schreibpfad NICHT (§9-Fallback).
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, braucht DB).
# ============================================================
from __future__ import annotations

from typing import Any

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.scenario import load_scenario_by_name
from foreman.core.pseudonymize import Pseudonymizer
from foreman.core.redact import Redactor
from foreman.ingestion.service import IngestionService
from foreman.substrate.client import SubstrateError

pytestmark = pytest.mark.integration


class _OkSubstrate:
    """Erreichbares Substrat — gibt eine Referenz zurück (mockt SubstrateClient)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def remember(self, content: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((content, metadata))
        return {"id": f"ref-{len(self.calls)}"}


class _FailSubstrate:
    """Nicht erreichbares Substrat — wirft bei jedem remember."""

    async def remember(self, content: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        raise SubstrateError("Substrat nicht erreichbar (Test)")


class _NoRefSubstrate:
    """Erreichbar, aber Antwort ohne verwertbare Referenz (z. B. {})."""

    async def remember(self, content: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"status": "ok"}  # keine id/memory_id/result → ref bleibt None


def _service(session: AsyncSession, pseudo: Pseudonymizer, redactor: Redactor, substrate: Any) -> IngestionService:
    return IngestionService(
        session, pseudonymizer=pseudo, redactor=redactor, substrate=substrate
    )


async def test_dual_write_setzt_substrate_ref_bei_erreichbarem_substrat(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    substrate = _OkSubstrate()
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    stats = await _service(db_session, pseudonymizer, fake_redactor, substrate).ingest(adapter)

    # alarm(1) + production_runs(2) + maintenance(1) = 4 semantische Ereignisse.
    total = await raw_conn.fetchval("SELECT count(*) FROM semantic_events")
    with_ref = await raw_conn.fetchval(
        "SELECT count(*) FROM semantic_events WHERE substrate_ref IS NOT NULL"
    )
    assert total == 4
    assert with_ref == 4
    assert stats.semantic_events == 4
    assert stats.substrate_refs == 4
    assert len(substrate.calls) == 4
    # Werker-Notizen werden NICHT ans Substrat gespiegelt (kein semantic_event).
    event_types = {
        row["event_type"] for row in await raw_conn.fetch("SELECT event_type FROM semantic_events")
    }
    assert event_types == {"alarm_raised", "production_run", "maintenance_performed"}


async def test_substrat_ausfall_blockiert_datenaufnahme_nicht(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    stats = await _service(db_session, pseudonymizer, fake_redactor, _FailSubstrate()).ingest(adapter)

    # Trotz Substrat-Ausfall: Readings + Ereignisse vollständig in der DB.
    assert await raw_conn.fetchval("SELECT count(*) FROM readings") == stats.readings_written > 0
    assert await raw_conn.fetchval("SELECT count(*) FROM alarms") == 1
    assert await raw_conn.fetchval("SELECT count(*) FROM production_runs") == 2
    assert await raw_conn.fetchval("SELECT count(*) FROM maintenance_events") == 1

    # semantic_events trotzdem gespiegelt, aber substrate_ref bleibt NULL.
    total = await raw_conn.fetchval("SELECT count(*) FROM semantic_events")
    with_ref = await raw_conn.fetchval(
        "SELECT count(*) FROM semantic_events WHERE substrate_ref IS NOT NULL"
    )
    assert total == 4
    assert with_ref == 0
    assert stats.substrate_refs == 0


async def test_substrat_ohne_verwertbare_referenz_bleibt_ref_null(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    # Substrat antwortet, liefert aber keine Referenz → Zeile geschrieben, ref NULL.
    await _service(db_session, pseudonymizer, fake_redactor, _NoRefSubstrate()).ingest(adapter)
    total = await raw_conn.fetchval("SELECT count(*) FROM semantic_events")
    with_ref = await raw_conn.fetchval(
        "SELECT count(*) FROM semantic_events WHERE substrate_ref IS NOT NULL"
    )
    assert total == 4
    assert with_ref == 0


async def test_ohne_substrat_konfiguration_bleibt_ref_null(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    # substrate=None (nicht konfiguriert) → kein remember-Versuch.
    await _service(db_session, pseudonymizer, fake_redactor, None).ingest(adapter)
    total = await raw_conn.fetchval("SELECT count(*) FROM semantic_events")
    with_ref = await raw_conn.fetchval(
        "SELECT count(*) FROM semantic_events WHERE substrate_ref IS NOT NULL"
    )
    assert total == 4
    assert with_ref == 0
