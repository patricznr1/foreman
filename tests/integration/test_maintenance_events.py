# ============================================================
#  FOREMAN — tests/integration/test_maintenance_events.py
#  Zweck: Pflicht-Test: Wartungsereignisse landen in maintenance_events;
#  performed_by ist tokenisiert (kein Klartext); als semantic_event gespiegelt.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, braucht DB).
# ============================================================
from __future__ import annotations

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.scenario import load_scenario_by_name
from foreman.core.pseudonymize import Pseudonymizer
from foreman.core.redact import Redactor
from foreman.ingestion.service import IngestionService

pytestmark = pytest.mark.integration


async def test_wartungsereignis_landet_mit_tokenisiertem_performed_by(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    await IngestionService(db_session, pseudonymizer=pseudonymizer, redactor=fake_redactor).ingest(
        adapter
    )

    rows = await raw_conn.fetch("SELECT type, description, performed_by FROM maintenance_events")
    assert len(rows) == 1
    event = rows[0]
    assert event["type"] == "lubrication"

    # performed_by ist tokenisiert (HMAC), NICHT der Klartext-Ref "U-1".
    token = event["performed_by"]
    assert token is not None
    assert token != "U-1"
    assert token.startswith("v1:")
    # Token entspricht der deterministischen Tokenisierung von "U-1".
    assert token == pseudonymizer.tokenize_worker("U-1")
    # Kein Klartext-Personenbezug in der Tabelle.
    assert "U-1" not in (event["description"] or "")


async def test_wartungsereignis_ist_als_semantic_event_gespiegelt(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    await IngestionService(db_session, pseudonymizer=pseudonymizer, redactor=fake_redactor).ingest(
        adapter
    )

    rows = await raw_conn.fetch(
        "SELECT payload FROM semantic_events WHERE event_type = 'maintenance_performed'"
    )
    assert len(rows) == 1
    # Im Payload steht der TOKEN, nie der Klartext-Ref.
    import json

    payload = rows[0]["payload"]
    payload = json.loads(payload) if isinstance(payload, str) else payload
    assert payload["type"] == "lubrication"
    assert payload["performed_by"] == pseudonymizer.tokenize_worker("U-1")
    assert payload["performed_by"] != "U-1"
