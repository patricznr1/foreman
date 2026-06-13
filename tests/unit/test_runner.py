# ============================================================
#  FOREMAN — tests/unit/test_runner.py
#  Zweck: Pflicht-Test-Block für den Simulations-Runner-Kern (F3).
#  Prüft: Modus-Auflösung ist fail-fast — unbekannte Modi scheitern hart, statt
#  stillschweigend auf Backfill zurückzufallen.
#  Architektur-Einordnung: Quality Gate §10.3 (Datenakquise, Simulations-Adapter).
# ============================================================
from __future__ import annotations

import pytest

from foreman.adapters.simulation.runner import WallClockPacer, _resolve_pace


def test_resolve_pace_backfill_ist_none() -> None:
    assert _resolve_pace("backfill", 1.0) is None


def test_resolve_pace_live_liefert_pacer() -> None:
    pace = _resolve_pace("live", 2.0)
    assert isinstance(pace, WallClockPacer)


def test_resolve_pace_unbekannter_mode_schlaegt_fehl() -> None:
    # Kein stiller Backfill-Fallback: unbekannte Modi müssen explizit scheitern.
    with pytest.raises(ValueError):
        _resolve_pace("bogus", 1.0)
