# ============================================================
#  FOREMAN — tests/integration/test_realtime_listener.py
#  Zweck: LISTEN-Consumer (F5) — eine dedizierte asyncpg-LISTEN-Verbindung
#         leitet NOTIFYs in den Hub. Verifiziert: (a) ein echtes pg_notify landet
#         im Hub und beim Abonnenten; (b) bei (Re)Connect ein breites Refresh
#         (Snapshot-Reload), das alle abonnierten Themen frisch markiert.
# ============================================================
from __future__ import annotations

import asyncio

import asyncpg
import pytest

from foreman.config import Settings
from foreman.realtime.channels import DASHBOARD_CHANNEL, ChangeSet, encode_change
from foreman.realtime.hub import DashboardHub
from foreman.realtime.listener import DashboardListener
from foreman.realtime.topics import machine_topic

pytestmark = pytest.mark.integration


def _dsn(settings: Settings) -> str:
    """Roher asyncpg-DSN aus der SQLAlchemy-URL (LISTEN braucht eine eigene Verbindung)."""
    return settings.database_url.replace("+asyncpg", "")


async def test_listener_forwards_notify_into_hub(
    test_settings: Settings, raw_conn: asyncpg.Connection
) -> None:
    hub = DashboardHub(debounce_seconds=0.01)
    listener = DashboardListener(_dsn(test_settings), hub)
    await listener.start()
    try:
        await asyncio.sleep(0.3)  # verbinden lassen (on-connect-broad ohne Abonnent)
        subscription = hub.register()
        hub.subscribe(subscription, machine_topic(5))

        await raw_conn.execute(
            "SELECT pg_notify($1, $2)",
            DASHBOARD_CHANNEL,
            encode_change(ChangeSet(machines=frozenset({5}))),
        )

        topic = await asyncio.wait_for(subscription.next_dirty(), timeout=2.0)
        assert topic == machine_topic(5)
    finally:
        await listener.stop()


async def test_listener_broad_refresh_on_connect(
    test_settings: Settings, raw_conn: asyncpg.Connection
) -> None:
    # Abonnent VOR start → der on-connect-broad (Snapshot-Reload) markiert sein Thema.
    hub = DashboardHub(debounce_seconds=0.01)
    subscription = hub.register()
    hub.subscribe(subscription, machine_topic(9))
    listener = DashboardListener(_dsn(test_settings), hub)
    await listener.start()
    try:
        topic = await asyncio.wait_for(subscription.next_dirty(), timeout=2.0)
        assert topic == machine_topic(9)
    finally:
        await listener.stop()
