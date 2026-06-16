# ============================================================
#  FOREMAN — tests/unit/test_realtime_topics.py
#  Zweck: Topic-Modell (F5) — Abbildung ChangeSet → betroffene WS-Themen.
#         Alarme (Maschinen) treffen Overview + Maschinen-Status; Readings
#         (Datenpunkte) treffen die Trend-Themen.
# ============================================================
from __future__ import annotations

from foreman.realtime.channels import ChangeSet
from foreman.realtime.topics import (
    OVERVIEW_TOPIC,
    machine_topic,
    parse_topic,
    topics_for_change,
    trend_topic,
)


def test_topic_helpers_format() -> None:
    assert OVERVIEW_TOPIC == "overview"
    assert machine_topic(5) == "machine:5"
    assert trend_topic(12) == "trend:12"


def test_machine_change_dirties_overview_and_machine_topic() -> None:
    assert topics_for_change(ChangeSet(machines=frozenset({5}))) == {
        OVERVIEW_TOPIC,
        machine_topic(5),
    }


def test_data_point_change_dirties_only_trend_topic() -> None:
    # Readings ändern den Trend, nicht den (alarm-getriebenen) Status.
    assert topics_for_change(ChangeSet(data_points=frozenset({12}))) == {trend_topic(12)}


def test_combined_change_unions_topics() -> None:
    topics = topics_for_change(ChangeSet(machines=frozenset({5, 7}), data_points=frozenset({12})))
    assert topics == {OVERVIEW_TOPIC, machine_topic(5), machine_topic(7), trend_topic(12)}


def test_empty_change_has_no_topics() -> None:
    assert topics_for_change(ChangeSet()) == set()


def test_parse_topic_recognises_kinds_and_ids() -> None:
    assert parse_topic(OVERVIEW_TOPIC) == ("overview", None)
    assert parse_topic(machine_topic(5)) == ("machine", 5)
    assert parse_topic(trend_topic(12)) == ("trend", 12)


def test_parse_topic_rejects_malformed_topics() -> None:
    assert parse_topic("garbage") == ("unknown", None)
    assert parse_topic("machine:abc") == ("unknown", None)
    assert parse_topic("machine:") == ("unknown", None)
    assert parse_topic("trend:") == ("unknown", None)
