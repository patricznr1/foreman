# ============================================================
#  FOREMAN — tests/unit/test_realtime_hub.py
#  Zweck: WS-Hub (F5) — Themen-Routing + serverseitiges debounce→signal.
#         Verifiziert Vorgabe 4 (debounce-then-load: der Hub coalesct Changes
#         pro Thema zu EINEM Signal; das Laden passiert danach im Endpoint) und
#         die kontrollierte Degradation (broad → alle abonnierten Themen frisch).
# ============================================================
from __future__ import annotations

import asyncio

from foreman.realtime.channels import ChangeSet
from foreman.realtime.hub import DashboardHub
from foreman.realtime.topics import OVERVIEW_TOPIC, machine_topic, trend_topic


async def test_subscriber_receives_its_dirty_topic() -> None:
    hub = DashboardHub(debounce_seconds=0.01)
    sub = hub.register()
    hub.subscribe(sub, machine_topic(5))

    hub.dispatch(ChangeSet(machines=frozenset({5})))

    topic = await asyncio.wait_for(sub.next_dirty(), timeout=1.0)
    assert topic == machine_topic(5)


async def test_overview_topic_dirtied_on_machine_change() -> None:
    hub = DashboardHub(debounce_seconds=0.01)
    sub = hub.register()
    hub.subscribe(sub, OVERVIEW_TOPIC)

    hub.dispatch(ChangeSet(machines=frozenset({5})))

    assert await asyncio.wait_for(sub.next_dirty(), timeout=1.0) == OVERVIEW_TOPIC


async def test_burst_is_coalesced_to_one_signal_per_topic() -> None:
    hub = DashboardHub(debounce_seconds=0.05)
    sub = hub.register()
    hub.subscribe(sub, machine_topic(5))

    # Zwei schnelle Changes im selben Fenster → genau EIN Signal (debounce).
    hub.dispatch(ChangeSet(machines=frozenset({5})))
    hub.dispatch(ChangeSet(machines=frozenset({5})))
    await asyncio.sleep(0.12)

    assert sub.queue.qsize() == 1


async def test_subscriber_does_not_receive_foreign_topics() -> None:
    hub = DashboardHub(debounce_seconds=0.01)
    sub = hub.register()
    hub.subscribe(sub, machine_topic(5))

    hub.dispatch(ChangeSet(machines=frozenset({7})))
    await asyncio.sleep(0.05)

    assert sub.queue.empty()


async def test_broad_change_dirties_all_subscribed_topics() -> None:
    hub = DashboardHub(debounce_seconds=0.01)
    sub = hub.register()
    hub.subscribe(sub, machine_topic(5))
    hub.subscribe(sub, trend_topic(12))

    hub.dispatch(ChangeSet(broad=True))
    await asyncio.sleep(0.05)

    received: set[str] = set()
    while not sub.queue.empty():
        received.add(sub.queue.get_nowait())
    assert received == {machine_topic(5), trend_topic(12)}


async def test_unsubscribe_stops_signals() -> None:
    hub = DashboardHub(debounce_seconds=0.01)
    sub = hub.register()
    hub.subscribe(sub, machine_topic(5))
    hub.unsubscribe(sub, machine_topic(5))

    hub.dispatch(ChangeSet(machines=frozenset({5})))
    await asyncio.sleep(0.05)

    assert sub.queue.empty()


async def test_remove_detaches_subscriber_from_all_topics() -> None:
    hub = DashboardHub(debounce_seconds=0.01)
    sub = hub.register()
    hub.subscribe(sub, machine_topic(5))
    hub.subscribe(sub, OVERVIEW_TOPIC)
    hub.remove(sub)

    hub.dispatch(ChangeSet(machines=frozenset({5})))
    await asyncio.sleep(0.05)

    assert sub.queue.empty()
    assert sub.topics == set()
