# ============================================================
#  FOREMAN — tests/unit/test_drift_validation_logic.py
#  Zweck: Pflicht-Test-Block für die reine Validierungs-Logik (F4, Baustein 6).
#  Prüft ohne DB: Offset->Zeit-Abbildung, ground_truth-Parsing (primary/control/
#  anchor), und die Kennzahlen-Berechnung (Fenster, Vorlauf, Fehlalarm, Kontrolle).
#  Architektur-Einordnung: Quality Gate §10.3 (Reasoner-Validierung).
# ============================================================
from __future__ import annotations

from datetime import timedelta

from foreman.adapters.simulation.scenario import load_scenario_by_name
from foreman.reasoners.drift.service import DriftFinding
from foreman.reasoners.drift.validation import (
    compute_metrics,
    event_time,
    load_truth,
    narrative_anchor,
)


def test_event_time_addiert_offset_auf_start() -> None:
    scenario = load_scenario_by_name("bearing_drift")
    assert event_time(scenario, "7d") == scenario.start_utc + timedelta(days=7)


def test_load_truth_liest_primary_und_anchor() -> None:
    scenario = load_scenario_by_name("bearing_drift")
    truth = load_truth(scenario)
    assert truth.drift_present is True
    assert truth.primary is not None
    assert truth.primary.data_point == "vib_rms"
    assert truth.primary.t_star == scenario.start_utc + timedelta(days=7)
    # Anker = die DEKLARIERTE erste menschliche Reaktion (Notiz "mahlendes
    # Geräusch", 16d14h) — NICHT der erste Alarm (17d08h). Bis 10.08.2026 wurde
    # der Anker aus den Alarmen abgeleitet; das schrieb dem Reasoner einen
    # Vorlauf gut, den er gegenüber dem Menschen nicht hatte.
    assert truth.anchor == scenario.start_utc + timedelta(days=16, hours=14)
    assert truth.anchor is not None
    assert truth.anchor < scenario.start_utc + timedelta(days=17, hours=8)


def test_narrative_anchor_faellt_ohne_deklaration_auf_ersten_alarm_zurueck() -> None:
    # Aufbau-Kontrolle zum Test darüber: Ohne deklarierten Anker greift der
    # Alarm-Fallback. Ohne diesen Zwilling wäre nicht unterscheidbar, ob der
    # Test oben den deklarierten Wert liest oder ob eine Ableitung zufällig
    # dasselbe Ergebnis liefert. `minimal_bearing_drift` trägt bewusst keinen
    # `human_reaction_offset`, aber einen Alarm.
    scenario = load_scenario_by_name("minimal_bearing_drift")
    assert scenario.ground_truth is not None
    assert "human_reaction_offset" not in (scenario.ground_truth.model_extra or {})
    erster_alarm = min(event_time(scenario, alarm.offset) for alarm in scenario.alarms)
    assert narrative_anchor(scenario) == erster_alarm


def test_load_truth_healthy_ist_driftfrei() -> None:
    truth = load_truth(load_scenario_by_name("healthy_baseline"))
    assert truth.drift_present is False
    assert truth.primary is None


def test_load_truth_control_signal_lubrication() -> None:
    truth = load_truth(load_scenario_by_name("lubrication_correlation"))
    assert "vib_rms_a" in truth.control_data_points  # Kontroll-Lager darf nicht melden


def test_narrative_anchor_ohne_alarme_ist_none() -> None:
    scenario = load_scenario_by_name("minimal_steady")
    assert narrative_anchor(scenario) is None


def test_metrics_drift_im_fenster_und_mit_vorlauf() -> None:
    scenario = load_scenario_by_name("bearing_drift")
    truth = load_truth(scenario)
    # Eine Meldung am Primär-Datenpunkt, im Fenster [7d, 10d] -> Fenster + Vorlauf.
    finding = DriftFinding(
        data_point_id=42,
        detected_at=scenario.start_utc + timedelta(days=8),
        effect_size=5.0,
    )
    metrics = compute_metrics([finding], {42: "vib_rms"}, truth)
    assert metrics.primary_detected_in_window is True
    assert metrics.detected_with_useful_lead is True
    assert metrics.false_alarms == 0


def test_metrics_drift_nach_fenster_aber_mit_vorlauf() -> None:
    scenario = load_scenario_by_name("bearing_drift")
    truth = load_truth(scenario)
    # Erst Tag 14 erkannt: außerhalb des engen Fensters, aber VOR dem Anker (17d08h).
    finding = DriftFinding(
        data_point_id=42,
        detected_at=scenario.start_utc + timedelta(days=14),
        effect_size=5.0,
    )
    metrics = compute_metrics([finding], {42: "vib_rms"}, truth)
    assert metrics.primary_detected_in_window is False
    assert metrics.detected_with_useful_lead is True  # Frühwarn-Nutzen erfüllt


def test_metrics_healthy_jede_meldung_ist_fehlalarm() -> None:
    scenario = load_scenario_by_name("healthy_baseline")
    truth = load_truth(scenario)
    finding = DriftFinding(
        data_point_id=7,
        detected_at=scenario.start_utc + timedelta(days=2),
        effect_size=5.0,
    )
    metrics = compute_metrics([finding], {7: "vib_rms"}, truth)
    assert metrics.false_alarms == 1
    assert metrics.detected_with_useful_lead is False


def test_metrics_control_signal_zaehlt_als_fehlalarm() -> None:
    scenario = load_scenario_by_name("lubrication_correlation")
    truth = load_truth(scenario)
    # Meldung am Kontroll-Lager (vib_rms_a) -> control_alarm + false_alarm.
    finding = DriftFinding(
        data_point_id=99,
        detected_at=scenario.start_utc + timedelta(days=5),
        effect_size=5.0,
    )
    metrics = compute_metrics([finding], {99: "vib_rms_a"}, truth)
    assert metrics.control_alarms == 1
    assert metrics.false_alarms >= 1
