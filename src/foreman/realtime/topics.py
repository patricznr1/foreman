# ============================================================
#  FOREMAN — realtime/topics.py
#  Zweck: Das Themen-Modell des Live-Push-Layers (F5): Bildung + Parsing der
#         WS-Themen und die Abbildung eines ChangeSet auf betroffene Themen.
#         EIN gemultiplexter Kanal, viele Themen-Abos: `overview` (Flotten-
#         Statusleiste/Cockpit), `machine:{id}` (komponierter Maschinen-Status)
#         und `trend:{data_point_id}` (Live-Sensortrend). Ein Alarm (Maschine)
#         trifft Overview + Maschinen-Status; ein Reading (Datenpunkt) den Trend.
#  Architektur-Einordnung: Live-Push-Layer (F5), reine Strings — ohne Transport,
#         direkt unit-testbar. `broad` behandelt der Hub gesondert (alle Abos).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from foreman.realtime.channels import ChangeSet

# Globales Flotten-/Statusleisten-Thema (Übersichts-Aggregation).
OVERVIEW_TOPIC = "overview"
_MACHINE_PREFIX = "machine:"
_TREND_PREFIX = "trend:"


def machine_topic(machine_id: int) -> str:
    """Thema für den komponierten Status einer einzelnen Maschine."""
    return f"{_MACHINE_PREFIX}{machine_id}"


def trend_topic(data_point_id: int) -> str:
    """Thema für den Live-Trend eines einzelnen Datenpunkts."""
    return f"{_TREND_PREFIX}{data_point_id}"


def parse_topic(topic: str) -> tuple[str, int | None]:
    """Zerlegt ein Thema in (Art, ID). Art ∈ {overview, machine, trend, unknown}.

    Ein unbekanntes oder fehlerhaftes Thema (z. B. ohne numerische ID) wird zu
    `("unknown", None)` — der Authorizer behandelt das als default-deny.
    """
    if topic == OVERVIEW_TOPIC:
        return ("overview", None)
    for kind, prefix in (("machine", _MACHINE_PREFIX), ("trend", _TREND_PREFIX)):
        if topic.startswith(prefix):
            rest = topic[len(prefix) :]
            return (kind, int(rest)) if rest.isdigit() else ("unknown", None)
    return ("unknown", None)


def topics_for_change(change: ChangeSet) -> set[str]:
    """Bildet ein (nicht-breites) ChangeSet auf die betroffenen WS-Themen ab.

    Maschinen-Änderungen (Alarme) treffen die Overview UND das Maschinen-Status-
    Thema; Datenpunkt-Änderungen (Readings) treffen das Trend-Thema. `broad`
    behandelt der Hub direkt (alle abonnierten Themen), daher hier nicht.
    """
    topics: set[str] = set()
    if change.machines:
        topics.add(OVERVIEW_TOPIC)
        topics.update(machine_topic(machine_id) for machine_id in change.machines)
    if change.data_points:
        topics.update(trend_topic(data_point_id) for data_point_id in change.data_points)
    return topics
