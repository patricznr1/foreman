# ============================================================
#  FOREMAN — tests/unit/test_live_stream.py
#  Zweck: Pflicht-Test-Block (Unit) für den Live-Daten-Stream-Produzenten:
#         - RealTimePacer (absoluter Wall-Clock-Takt, kein Warten in der Vergangenheit),
#         - live_tick_times (lückenlose, überlappungsfreie Tick-Zeitachse),
#         - die wiederverwendbaren SimulationAdapter-Nähte (tick_readings/new_rngs/
#           end_elapsed_s/local_timezone) inkl. Plateau-Ehrlichkeit der Drift.
#  Architektur-Einordnung: Quality Gate §10.3 (Datenakquise, Live-Adapter). Rein,
#         ohne DB — die DB-Integration deckt tests/integration/test_live_worker.py.
# ============================================================
from __future__ import annotations

from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.live import (
    RealTimePacer,
    cap_resume_anchor,
    live_tick_times,
)
from foreman.adapters.simulation.scenario import load_scenario_by_name
from foreman.adapters.simulation.signals import drift_offset
from foreman.ingestion.normalized import NormalizedReading

# --- Test-Helfer ---------------------------------------------------------------


class _RecordingSleep:
    """Zeichnet die angeforderten Sleep-Dauern auf, ohne real zu warten."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, delay: float) -> Awaitable[None]:
        self.delays.append(delay)

        async def _noop() -> None:
            return None

        return _noop()


def _fake_dp_ids(scenario_name: str) -> dict[str, int]:
    """Fake-ID-Auflösung (ohne DB) — je Datenpunkt-Key eine stabile Pseudo-ID."""
    scenario = load_scenario_by_name(scenario_name)
    return {dp.key: idx + 1 for idx, dp in enumerate(scenario.data_points)}


# --- RealTimePacer -------------------------------------------------------------


async def test_realtime_pacer_wartet_nicht_in_der_vergangenheit() -> None:
    # Aufhol-Phase: liegt der Ziel-Stempel vor 'now', wird NICHT gewartet.
    now = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)
    sleep = _RecordingSleep()
    pacer = RealTimePacer(now=lambda: now, sleep=sleep)

    await pacer(now - timedelta(minutes=10))

    assert sleep.delays == []
    assert pacer.tick_count == 1


async def test_realtime_pacer_wartet_exakte_differenz_in_die_zukunft() -> None:
    # Live-Phase: liegt das Ziel in der Zukunft, wird genau bis dahin gewartet.
    now = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)
    sleep = _RecordingSleep()
    pacer = RealTimePacer(now=lambda: now, sleep=sleep)

    await pacer(now + timedelta(seconds=30))

    assert sleep.delays == [pytest.approx(30.0)]


async def test_realtime_pacer_normalisiert_naive_ziele_als_utc() -> None:
    # Naive Stempel werden als UTC interpretiert (Normalform-Vertrag) — kein Crash.
    now = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)
    sleep = _RecordingSleep()
    pacer = RealTimePacer(now=lambda: now, sleep=sleep)

    await pacer(datetime(2026, 6, 25, 11, 50, 0))  # naiv, in der Vergangenheit

    assert sleep.delays == []


# --- live_tick_times -----------------------------------------------------------


def test_live_tick_times_setzt_strikt_nach_anker_an() -> None:
    # Erster Tick = anchor + interval → strikt NACH dem letzten Historien-Stempel
    # (kein Overlap mit der Historie, PK (data_point_id, time) kollidiert nie).
    anchor = datetime(2026, 6, 21, 6, 0, 0, tzinfo=UTC)
    interval = timedelta(minutes=10)

    times = list(live_tick_times(anchor, interval, max_ticks=3))

    assert times[0] == anchor + interval
    assert all(t > anchor for t in times)


def test_live_tick_times_ist_lueckenlos_und_monoton() -> None:
    # Konstanter Abstand = interval (kein Gap), streng monoton steigend.
    anchor = datetime(2026, 6, 21, 6, 0, 0, tzinfo=UTC)
    interval = timedelta(minutes=10)

    times = list(live_tick_times(anchor, interval, max_ticks=5))

    assert len(times) == 5
    diffs = [b - a for a, b in pairwise(times)]
    assert all(d == interval for d in diffs)


def test_live_tick_times_respektiert_max_ticks() -> None:
    anchor = datetime(2026, 6, 21, 6, 0, 0, tzinfo=UTC)
    times = list(live_tick_times(anchor, timedelta(seconds=5), max_ticks=0))
    assert times == []


def test_live_tick_times_lehnt_nicht_positives_intervall_ab() -> None:
    anchor = datetime(2026, 6, 21, 6, 0, 0, tzinfo=UTC)
    with pytest.raises(ValueError):
        list(live_tick_times(anchor, timedelta(0), max_ticks=1))


# --- cap_resume_anchor (opt-in Aufhol-Deckel) ----------------------------------


def test_cap_resume_anchor_ohne_deckel_fuellt_die_luecke() -> None:
    # Default (None): kein Deckel → der echte letzte Stempel bleibt Anker (kein Gap).
    now = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)
    last = now - timedelta(days=30)  # riesige Lücke
    assert cap_resume_anchor(last, now=now, interval=timedelta(seconds=60), max_catchup_ticks=None) == last


def test_cap_resume_anchor_innerhalb_des_deckels_unveraendert() -> None:
    # Lücke ≤ max_catchup_ticks·interval → normaler lückenloser Aufholpfad.
    now = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)
    interval = timedelta(seconds=60)
    last = now - 500 * interval  # 500 < 1000 Ticks
    assert cap_resume_anchor(last, now=now, interval=interval, max_catchup_ticks=1000) == last


def test_cap_resume_anchor_jenseits_des_deckels_springt_auf_now() -> None:
    # Lücke > max_catchup_ticks·interval → bewusste (geloggte) Lücke: Start bei now.
    now = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)
    interval = timedelta(seconds=60)
    last = now - 5000 * interval  # 5000 > 1000 Ticks → kein Boot-Storm
    capped = cap_resume_anchor(last, now=now, interval=interval, max_catchup_ticks=1000)
    assert capped == now - interval


# --- SimulationAdapter-Nähte (wiederverwendbar für den Live-Lauf) --------------


def test_end_elapsed_s_ist_letzter_backfill_tick() -> None:
    # Plateau-Anker: verstrichene Sim-Sekunden am LETZTEN Backfill-Tick.
    adapter = SimulationAdapter(load_scenario_by_name("minimal_steady"), seed=7)
    scenario = adapter.scenario
    interval_s = scenario.interval_delta.total_seconds()
    tick_count = int(scenario.duration_delta.total_seconds() // interval_s)

    assert adapter.end_elapsed_s() == (tick_count - 1) * interval_s
    assert adapter.end_elapsed_s() >= 0


def test_tick_readings_ist_deterministisch_bei_gleichem_seed() -> None:
    # Gleicher Seed + gleiche Eingaben → byte-identische Werte (Reproduzierbarkeit).
    dp_ids = _fake_dp_ids("minimal_bearing_drift")
    utc_time = datetime(2026, 6, 25, 10, 0, 0, tzinfo=UTC)

    def _emit() -> list[NormalizedReading]:
        adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=42)
        local_dt = utc_time.astimezone(adapter.local_timezone)
        return list(
            adapter.tick_readings(
                utc_time=utc_time,
                local_dt=local_dt,
                elapsed_s=adapter.end_elapsed_s(),
                rngs=adapter.new_rngs(),
                data_point_ids=dp_ids,
            )
        )

    first, second = _emit(), _emit()
    assert [r.value for r in first] == [r.value for r in second]
    assert all(r.time == utc_time for r in first)


def test_tick_readings_traegt_den_uebergebenen_zeitstempel() -> None:
    # Wall-Clock-Stempel: der Tick trägt EXAKT die übergebene Zeit (nie Sim-Zeit).
    dp_ids = _fake_dp_ids("minimal_steady")
    adapter = SimulationAdapter(load_scenario_by_name("minimal_steady"), seed=1)
    wall_clock = datetime(2026, 6, 25, 14, 30, 0, tzinfo=UTC)

    readings = list(
        adapter.tick_readings(
            utc_time=wall_clock,
            local_dt=wall_clock.astimezone(adapter.local_timezone),
            elapsed_s=adapter.end_elapsed_s(),
            rngs=adapter.new_rngs(),
            data_point_ids=dp_ids,
        )
    )

    assert readings, "ein Tick muss mindestens einen Datenpunkt liefern"
    assert all(r.time == wall_clock for r in readings)


def test_live_drift_plateau_waechst_nicht_ueber_die_ticks() -> None:
    # Plateau-Ehrlichkeit: über die Live-Ticks bleibt elapsed_s konstant auf
    # end_elapsed_s — die Drift wird am Historien-Stand GEHALTEN, nicht (wie im
    # Backfill) weitergetrieben. Belegt über zwei Ticks 7 Tage auseinander mit
    # gleicher Tageszeit/Schicht + frischem identischem Seed: identische Werte =
    # die Drift hängt am Plateau, nicht an der fortschreitenden Zeit.
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=7)
    dp_ids = _fake_dp_ids("minimal_bearing_drift")
    plateau = adapter.end_elapsed_s()
    tz = adapter.local_timezone

    t1 = datetime(2026, 6, 25, 10, 0, 0, tzinfo=UTC)  # Donnerstag, Frühschicht
    t2 = t1 + timedelta(days=7)  # gleicher Wochentag + Tageszeit → gleiche Schicht-Last

    def _values(at: datetime) -> list[float]:
        return [
            r.value
            for r in adapter.tick_readings(
                utc_time=at,
                local_dt=at.astimezone(tz),
                elapsed_s=plateau,
                rngs=adapter.new_rngs(),
                data_point_ids=dp_ids,
            )
        ]

    assert _values(t1) == _values(t2), "Plateau: gleiche Tageszeit → identisch (kein Weglaufen)"

    # Zusätzlich: der gehaltene Drift-Offset überschreitet das Ziel nie (kein Überschwingen).
    spec = next(p.profile.drift for p in adapter._plans if p.profile and p.profile.drift)
    assert drift_offset(spec, plateau) <= spec.target_delta + 1e-9


def test_gesunde_maschine_erfindet_kein_signal() -> None:
    # Ehrlichkeitslinie: eine gesunde Maschine (kein drift-Block) trägt im Live-Lauf
    # KEINE Drift — nur Baseline + Rauschen. Belegt (a) kein analoger Datenpunkt hat
    # eine Drift-Spec, (b) zwei weit auseinanderliegende Ticks (gleiche Tageszeit)
    # liefern identische Werte → kein über die Zeit wachsendes/erfundenes Signal.
    adapter = SimulationAdapter(load_scenario_by_name("minimal_steady"), seed=3)
    dp_ids = _fake_dp_ids("minimal_steady")
    plateau = adapter.end_elapsed_s()
    tz = adapter.local_timezone

    assert all(p.profile.drift is None for p in adapter._plans if p.profile)

    t1 = datetime(2026, 6, 25, 10, 0, 0, tzinfo=UTC)  # Donnerstag, Frühschicht
    t2 = t1 + timedelta(days=28)  # gleicher Wochentag + Tageszeit (4 Wochen)

    def _values(at: datetime) -> list[float]:
        return [
            r.value
            for r in adapter.tick_readings(
                utc_time=at,
                local_dt=at.astimezone(tz),
                elapsed_s=plateau,
                rngs=adapter.new_rngs(),
                data_point_ids=dp_ids,
            )
        ]

    assert _values(t1) == _values(t2), "gesund: kein wachsendes Signal über die Zeit"


def test_local_timezone_ist_tz_aware() -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_steady"), seed=1)
    assert adapter.local_timezone is not None
    # Park-Szenarien laufen in lokaler Werkszeit (+02:00) — Offset existiert.
    assert adapter.local_timezone.utcoffset(datetime(2026, 6, 25, 12, 0, 0)) is not None
