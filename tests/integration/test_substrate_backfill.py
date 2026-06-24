# ============================================================
#  FOREMAN — tests/integration/test_substrate_backfill.py
#  Zweck: Backfill gegen die echte (Timescale-)DB — prüft die reale SQL-Auswahl
#         (nur substrate_ref IS NULL, Keyset-Pagination) + Persistenz der Referenz
#         + DB-seitige Idempotenz. Ergänzt die DB-freien Unit-Tests.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, braucht DB).
# ============================================================
from __future__ import annotations

from typing import Any

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import SemanticEvent
from foreman.substrate.backfill import backfill_semantic_events

pytestmark = pytest.mark.integration


class _OkSubstrate:
    """Erreichbares Substrat — liefert je remember eine Referenz."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def remember(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls.append((content, metadata))
        return {"id": f"ref-{len(self.calls)}"}


def _maint_payload(machine_id: int) -> dict[str, Any]:
    return {
        "type": "inspection",
        "machine_id": machine_id,
        "component_id": None,
        "performed_at": "2026-06-01T00:00:00+00:00",
        "performed_by": None,
    }


async def _seed_rows(session: AsyncSession) -> None:
    # 3 NULL-ref-Zeilen + 1 bereits gespiegelte (machine_id=None: keine FK-Seed nötig).
    session.add_all(
        [
            SemanticEvent(
                machine_id=None,
                event_type="maintenance_performed",
                payload=_maint_payload(1),
                substrate_ref=None,
            ),
            SemanticEvent(
                machine_id=None,
                event_type="maintenance_performed",
                payload=_maint_payload(2),
                substrate_ref=None,
            ),
            SemanticEvent(
                machine_id=None,
                event_type="maintenance_performed",
                payload=_maint_payload(3),
                substrate_ref=None,
            ),
            SemanticEvent(
                machine_id=None,
                event_type="maintenance_performed",
                payload=_maint_payload(4),
                substrate_ref="bereits-da",
            ),
        ]
    )
    await session.commit()


async def test_backfill_setzt_nur_null_refs_in_db(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
) -> None:
    await _seed_rows(db_session)
    sub = _OkSubstrate()

    stats = await backfill_semantic_events(db_session, sub, batch_size=2)

    # Nur die 3 NULL-ref-Zeilen wurden gespiegelt; die vorbelegte blieb unberührt.
    assert stats.refs_set == 3
    assert len(sub.calls) == 3
    null_count = await raw_conn.fetchval(
        "SELECT count(*) FROM semantic_events WHERE substrate_ref IS NULL"
    )
    assert null_count == 0
    untouched = await raw_conn.fetchval(
        "SELECT substrate_ref FROM semantic_events WHERE payload->>'machine_id' = '4'"
    )
    assert untouched == "bereits-da"


async def test_backfill_ist_in_der_db_idempotent(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
) -> None:
    await _seed_rows(db_session)

    first = await backfill_semantic_events(db_session, _OkSubstrate())
    assert first.refs_set == 3

    # Zweiter Lauf: nichts mehr NULL → kein remember, keine Änderung.
    sub2 = _OkSubstrate()
    second = await backfill_semantic_events(db_session, sub2)
    assert second.scanned == 0
    assert len(sub2.calls) == 0
    total = await raw_conn.fetchval("SELECT count(*) FROM semantic_events")
    assert total == 4  # additiv: keine neuen Zeilen


async def test_backfill_cross_batch_pagination_in_db(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
) -> None:
    # 7 NULL-Zeilen, batch_size=3 → echte Keyset-Pagination über 3 Fetch-Seiten.
    db_session.add_all(
        [
            SemanticEvent(
                machine_id=None,
                event_type="maintenance_performed",
                payload=_maint_payload(i),
                substrate_ref=None,
            )
            for i in range(1, 8)
        ]
    )
    await db_session.commit()

    sub = _OkSubstrate()
    stats = await backfill_semantic_events(db_session, sub, batch_size=3)

    assert stats.refs_set == 7
    assert len(sub.calls) == 7
    # Jede Zeile genau einmal gesendet (keine Dublette, keine Lücke).
    sent = sorted(meta["machine_id"] for _content, meta in sub.calls if meta is not None)
    assert sent == list(range(1, 8))
    null_count = await raw_conn.fetchval(
        "SELECT count(*) FROM semantic_events WHERE substrate_ref IS NULL"
    )
    assert null_count == 0
