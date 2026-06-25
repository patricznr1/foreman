# ============================================================
#  FOREMAN — tests/unit/test_reads_stream.py
#  Zweck: Reine Klassifikation des Eingangs-Stream-Status (Zwilling als
#         Datenquelle): aus dem jüngsten Reading-Stempel + Frischefenster wird
#         ehrlich aktiv/inaktiv abgeleitet — ohne DB, direkt testbar. Dies ist die
#         EINE Wahrheit, die Topologie-Kachel und Live-Badge gemeinsam tragen.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from foreman.reads.stream import STREAM_FRESH_WINDOW, classify_stream

_NOW = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
_WINDOW = timedelta(minutes=5)


def test_no_reading_is_inactive() -> None:
    # Nie ein Wall-Clock-Reading → der Worker tickt nicht (ehrlich inaktiv).
    assert classify_stream(None, now=_NOW, fresh_window=_WINDOW) is False


def test_fresh_reading_is_active() -> None:
    # Jüngstes Reading im Frischefenster → der Worker tickt (aktiv).
    assert classify_stream(_NOW - timedelta(minutes=2), now=_NOW, fresh_window=_WINDOW) is True


def test_reading_exactly_at_window_edge_is_active() -> None:
    # Genau an der Fenstergrenze zählt noch als frisch (>=, nicht >).
    assert classify_stream(_NOW - _WINDOW, now=_NOW, fresh_window=_WINDOW) is True


def test_stale_reading_is_inactive() -> None:
    # Älter als das Fenster → nur Historie, kein laufender Stream.
    assert classify_stream(_NOW - timedelta(minutes=10), now=_NOW, fresh_window=_WINDOW) is False


def test_naive_timestamp_treated_as_utc() -> None:
    # Defensiv: ein naiver Stempel wird als UTC interpretiert, nicht zum Crash.
    naive = datetime(2026, 6, 25, 11, 58)
    assert classify_stream(naive, now=_NOW, fresh_window=_WINDOW) is True


def test_default_window_is_five_minutes() -> None:
    # Bewusster Demo-Wert (Worker-Default-Takt 60s): toleriert ~5 verpasste Ticks,
    # erkennt einen gestoppten Worker binnen 5 min. Anker gegen versehentliche Drift.
    assert STREAM_FRESH_WINDOW == timedelta(minutes=5)
