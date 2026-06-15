# ============================================================
#  FOREMAN — reasoners/drift/validation.py
#  Zweck: Validierung des Drift-Reasoners gegen die Szenario-Wahrheit (F4,
#         Baustein 6, Research §7). Liest den `ground_truth`-Block eines
#         Szenarios, bildet die Offsets (t*, Erkennungsfenster) auf absolute
#         Zeiten ab und berechnet aus den Replay-Findings die Kennzahlen
#         Detektionsverzug, Treffer-im-Fenster, Fehlalarmrate und MTFA.
#  Architektur-Einordnung: Reasoning-Schicht (F4). Reine, seedbare Auswertung
#         (ohne DB testbar); der Replay selbst liefert die Findings.
# ============================================================
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from foreman.adapters.simulation.scenario import Scenario, parse_duration
from foreman.reasoners.drift.service import DriftFinding


def event_time(scenario: Scenario, offset: str) -> datetime:
    """Absolute (tz-aware UTC) Zeit eines Szenario-Offsets ab `scenario.start`."""
    return scenario.start_utc + parse_duration(offset)


@dataclass(frozen=True)
class PrimaryDriftTruth:
    """Die erwartete Primär-Drift eines Szenarios (aus ground_truth.primary_drift)."""

    data_point: str
    t_star: datetime
    window_start: datetime
    window_end: datetime


@dataclass(frozen=True)
class ScenarioTruth:
    """Validierungs-Wahrheit eines Szenarios (ground_truth-Block).

    `anchor` ist der narrative Anker = früheste Alarm-/Werker-Reaktion im Szenario.
    Der betriebliche Frühwarn-Nutzen ist erfüllt, wenn die Drift VOR diesem Anker
    erkannt wird (Research §7: nützlicher Vorlauf in Tagen). Das enge
    expected_detection_window ist eine optimistische Zielgröße — bei progressiven
    Ramps ist das Signal dort noch im Rauschen (an Realdaten zu schärfen).
    """

    drift_present: bool
    expected_false_alarms: int
    primary: PrimaryDriftTruth | None
    # Korrelierte Mit-Signale (ground_truth.secondary_confirmation): eine Erkennung
    # daran bestätigt dieselbe physikalische Drift (z. B. Spindelstrom ∝ -Moment).
    secondary_data_points: tuple[str, ...]
    control_data_points: tuple[str, ...]
    anchor: datetime | None


def narrative_anchor(scenario: Scenario) -> datetime | None:
    """Früheste Alarm-Zeit eines Szenarios (Vorlauf-Deadline), oder None."""
    if not scenario.alarms:
        return None
    return min(event_time(scenario, alarm.offset) for alarm in scenario.alarms)


def load_truth(scenario: Scenario) -> ScenarioTruth:
    """Liest den ground_truth-Block (Pydantic extra='allow') in eine ScenarioTruth.

    `primary_drift` und `control_signal` liegen als Extra-Felder vor (F3 validiert
    nur `drift_present`/`expected_false_alarms` strikt; die Detail-Struktur ist
    F4-Domäne).
    """
    gt = scenario.ground_truth
    if gt is None:
        raise ValueError(f"Szenario '{scenario.scenario.name}' hat keinen ground_truth-Block.")
    extra: Mapping[str, object] = gt.model_extra or {}

    primary: PrimaryDriftTruth | None = None
    primary_raw = extra.get("primary_drift")
    if isinstance(primary_raw, Mapping):
        window = primary_raw.get("expected_detection_window")
        t_star = str(primary_raw["t_star"])
        if isinstance(window, Sequence) and len(window) == 2:
            window_start = event_time(scenario, str(window[0]))
            window_end = event_time(scenario, str(window[1]))
        else:  # Fallback: ab t* offen
            window_start = event_time(scenario, t_star)
            window_end = scenario.start_utc + scenario.duration_delta
        primary = PrimaryDriftTruth(
            data_point=str(primary_raw["data_point"]),
            t_star=event_time(scenario, t_star),
            window_start=window_start,
            window_end=window_end,
        )

    def _data_points(key: str) -> list[str]:
        raw = extra.get(key)
        names: list[str] = []
        if isinstance(raw, Sequence) and not isinstance(raw, str):
            for item in raw:
                if isinstance(item, Mapping) and "data_point" in item:
                    names.append(str(item["data_point"]))
        return names

    return ScenarioTruth(
        drift_present=gt.drift_present,
        expected_false_alarms=gt.expected_false_alarms,
        primary=primary,
        secondary_data_points=tuple(_data_points("secondary_confirmation")),
        control_data_points=tuple(_data_points("control_signal")),
        anchor=narrative_anchor(scenario),
    )


@dataclass(frozen=True)
class DriftMetrics:
    """Abnahme-Kennzahlen eines Validierungslaufs (Research §7)."""

    findings_count: int
    primary_detected_in_window: bool  # im engen ground_truth-Fenster (optimistisch)
    detected_with_useful_lead: bool  # nach t* UND vor dem narrativen Anker (Frühwarn-Nutzen)
    detection_delay: timedelta | None  # t* -> erste Primär-Meldung
    false_alarms: int  # Meldungen außerhalb der Erwartung
    control_alarms: int  # Meldungen am Kontroll-Signal (müssen 0 sein)


def compute_metrics(
    findings: Sequence[DriftFinding],
    name_by_id: Mapping[int, str],
    truth: ScenarioTruth,
) -> DriftMetrics:
    """Berechnet die Abnahme-Kennzahlen aus den Findings gegen die Szenario-Wahrheit.

    `name_by_id` bildet die data_point-DB-ID auf den Szenario-Namen ab.
    """
    named = [(name_by_id.get(f.data_point_id, ""), f) for f in findings]

    control_alarms = sum(1 for name, _ in named if name in truth.control_data_points)

    if not truth.drift_present:
        # Negativkontrolle: jede Meldung ist ein Fehlalarm.
        return DriftMetrics(
            findings_count=len(findings),
            primary_detected_in_window=False,
            detected_with_useful_lead=False,
            detection_delay=None,
            false_alarms=len(findings),
            control_alarms=control_alarms,
        )

    assert truth.primary is not None  # drift_present -> primary erwartet
    # Die Drift gilt als erkannt, wenn das primary ODER ein korreliertes
    # secondary_confirmation-Signal meldet (dieselbe physikalische Ursache).
    accepted = {truth.primary.data_point, *truth.secondary_data_points}
    primary_hits = sorted(
        (f for name, f in named if name in accepted),
        key=lambda f: f.detected_at,
    )
    in_window = False
    useful_lead = False
    delay: timedelta | None = None
    if primary_hits:
        first = primary_hits[0]
        delay = first.detected_at - truth.primary.t_star
        in_window = truth.primary.window_start <= first.detected_at <= truth.primary.window_end
        before_anchor = truth.anchor is None or first.detected_at < truth.anchor
        useful_lead = first.detected_at >= truth.primary.t_star and before_anchor

    # Fehlalarm: Meldungen am Kontroll-Signal + Primär-Meldungen vor t*.
    early_primary = sum(1 for f in primary_hits if f.detected_at < truth.primary.t_star)
    return DriftMetrics(
        findings_count=len(findings),
        primary_detected_in_window=in_window,
        detected_with_useful_lead=useful_lead,
        detection_delay=delay,
        false_alarms=control_alarms + early_primary,
        control_alarms=control_alarms,
    )
