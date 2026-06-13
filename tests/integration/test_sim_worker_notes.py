# ============================================================
#  FOREMAN — tests/integration/test_sim_worker_notes.py
#  Zweck: Pflicht-Test: Szenario-Werker-Notizen laufen durch den F2-Schreibpfad —
#  Freitext NER-maskiert (kein Klartext-Name), author tokenisiert (kein Klartext).
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


async def test_werker_notizen_sind_ner_maskiert_und_autor_tokenisiert(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    await IngestionService(
        db_session, pseudonymizer=pseudonymizer, redactor=fake_redactor
    ).ingest(adapter)

    rows = await raw_conn.fetch("SELECT text, author, shift FROM worker_notes ORDER BY created_at")
    assert len(rows) == 2

    # Notiz 1 enthielt den Namen "Schmidt" → maskiert zu [PERSON], kein Klartext.
    note_with_name = rows[0]
    assert "Schmidt" not in note_with_name["text"]
    assert "[PERSON]" in note_with_name["text"]

    # Autoren sind tokenisiert (HMAC), nicht der Klartext-Ref.
    for row in rows:
        author = row["author"]
        assert author is not None
        assert author.startswith("v1:")
        assert author not in ("U-2", "U-3")
    assert rows[0]["author"] == pseudonymizer.tokenize_worker("U-2")
    assert rows[1]["author"] == pseudonymizer.tokenize_worker("U-3")


async def test_werker_notizen_tragen_historische_zeit(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # created_at wird auf die Szenario-Zeit gesetzt (nicht server-default now()).
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    await IngestionService(
        db_session, pseudonymizer=pseudonymizer, redactor=fake_redactor
    ).ingest(adapter)

    # Szenario-Start 2026-05-04 → Notizen liegen im Mai 2026, nicht "heute".
    years = {
        row["y"]
        for row in await raw_conn.fetch(
            "SELECT EXTRACT(YEAR FROM created_at)::int AS y FROM worker_notes"
        )
    }
    assert years == {2026}
    earliest = await raw_conn.fetchval("SELECT min(created_at) FROM worker_notes")
    assert earliest.year == 2026
    assert earliest.month == 5
