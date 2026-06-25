# ============================================================
#  FOREMAN — tests/integration/test_reads_stream.py
#  Zweck: Read-Core Eingangs-Stream-Status (Zwilling als Datenquelle). Leitet aus
#         dem jüngsten `readings`-Stempel der internen Simulationsquelle ehrlich
#         aktiv/inaktiv ab — getrennt von externen Quellen (opcua etc.). Speist
#         Topologie-Kachel UND Live-Badge mit DERSELBEN Wahrheit.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import DataPoint, Machine, Reading
from foreman.reads.stream import build_stream_status

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
_WINDOW = timedelta(minutes=5)


async def _seed_reading(session: AsyncSession, *, source: str, at: datetime | None) -> None:
    """Legt Maschine + Datenpunkt einer Quelle an, optional mit einem Reading bei `at`."""
    machine = Machine(label=f"M-{source}")
    session.add(machine)
    await session.flush()
    dp = DataPoint(machine_id=machine.id, name=f"dp-{source}", kind="analog", source=source)
    session.add(dp)
    await session.flush()
    if at is not None:
        session.add(Reading(data_point_id=dp.id, time=at, value=1.0))
    await session.commit()


async def test_active_when_recent_simulation_reading(db_session: AsyncSession) -> None:
    await _seed_reading(db_session, source="simulation", at=_NOW - timedelta(minutes=1))

    status = await build_stream_status(db_session, now=_NOW, fresh_window=_WINDOW)

    assert status.active is True
    assert status.last_reading_at == _NOW - timedelta(minutes=1)


async def test_inactive_when_only_stale_simulation_readings(db_session: AsyncSession) -> None:
    # Geseedete Historie (alt) ohne tickenden Worker → inaktiv, aber Stand bleibt sichtbar.
    await _seed_reading(db_session, source="simulation", at=_NOW - timedelta(hours=3))

    status = await build_stream_status(db_session, now=_NOW, fresh_window=_WINDOW)

    assert status.active is False
    assert status.last_reading_at == _NOW - timedelta(hours=3)


async def test_inactive_without_stamp_when_no_simulation_source(db_session: AsyncSession) -> None:
    # Nur eine externe Quelle vorhanden → kein Eingangs-Stream, kein Stand.
    await _seed_reading(db_session, source="opcua", at=_NOW - timedelta(minutes=1))

    status = await build_stream_status(db_session, now=_NOW, fresh_window=_WINDOW)

    assert status.active is False
    assert status.last_reading_at is None


async def test_ignores_other_sources_freshness(db_session: AsyncSession) -> None:
    # Eine frische externe Quelle darf den Sim-Stream NICHT fälschlich aktiv machen.
    await _seed_reading(db_session, source="opcua", at=_NOW - timedelta(seconds=10))
    await _seed_reading(db_session, source="simulation", at=_NOW - timedelta(hours=2))

    status = await build_stream_status(db_session, now=_NOW, fresh_window=_WINDOW)

    assert status.active is False
    assert status.last_reading_at == _NOW - timedelta(hours=2)
