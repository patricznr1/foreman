# ============================================================
#  FOREMAN — tests/unit/test_park_scenarios.py
#  Zweck: Pflicht-Test (ohne DB): die 12 Twin-Park-Szenarien laden + validieren
#         gegen das strikte scenario.py-Schema; Negativkontrollen driften nicht;
#         Degradations-Dateien tragen einen prueffaehigen ground_truth-Block;
#         szenarien.md deckt alle Muster ab.
#  Architektur-Einordnung: Quality Gate §10.3 (Unit, kein DB-Zugriff).
# ============================================================
from __future__ import annotations

from pathlib import Path

import pytest

from foreman.adapters.simulation.park import (
    PARK_LINE_LABEL,
    park_scenario_paths,
)
from foreman.adapters.simulation.scenario import GroundTruth, Scenario, load_scenario_file

# Erwartete Park-Belegung (Design "Montagelinie 1", Abschnitt A).
EXPECTED_MACHINES: dict[str, str] = {
    "FD-01": "feeder",
    "FD-02": "feeder",
    "PR-01": "servo_press",
    "PR-02": "servo_press",
    "PR-03": "servo_press",
    "AX-01": "servo_axis",
    "AX-02": "servo_axis",
    "AX-03": "servo_axis",
    "AX-04": "servo_axis",
    "RB-01": "robot",
    "RB-02": "robot",
    "VS-01": "vision",
}

# Schwestern mit eingebauter Degradation (drift_present=true).
DRIFT_MACHINES = {"FD-02", "PR-01", "PR-02", "AX-02", "AX-03", "VS-01"}
# Negativkontrollen / gesunde Schwestern (drift_present=false, KEIN drift-Block).
HEALTHY_MACHINES = {"FD-01", "PR-03", "AX-01", "AX-04", "RB-01", "RB-02"}

# Datei-Stem -> erwartetes #4-Kausalmuster (maintenance_causal.pattern).
EXPECTED_PATTERNS: dict[str, str] = {
    "park_fd01": "control",
    "park_fd02": "wear_not_maintenance_caused",
    "park_pr01": "wear_not_maintenance_caused",
    "park_pr02": "interval_too_long_and_skipped_inspection",
    "park_pr03": "control",
    "park_ax01": "control",
    "park_ax02": "grease_choice",
    "park_ax03": "overload_not_maintenance_caused",
    "park_ax04": "interval_too_short",
    "park_rb01": "control",
    "park_rb02": "control",
    "park_vs01": "effect_not_maintenance_caused",
}

SZENARIEN_DOC = Path(__file__).resolve().parents[2] / "docs" / "simulation" / "szenarien.md"


def _load_all() -> dict[str, Scenario]:
    """Laedt alle Park-Szenarien, key = external_id."""
    out: dict[str, Scenario] = {}
    for path in park_scenario_paths():
        scenario = load_scenario_file(path)
        out[scenario.machine.external_id] = scenario
    return out


def _gt(scenario: Scenario) -> GroundTruth:
    """ground_truth einer Park-Datei (in jedem Park-Szenario vorhanden)."""
    assert scenario.ground_truth is not None
    return scenario.ground_truth


def test_genau_zwoelf_park_dateien() -> None:
    paths = park_scenario_paths()
    assert len(paths) == 12
    assert all(p.stem.startswith("park_") for p in paths)


def test_alle_park_szenarien_laden_und_validieren() -> None:
    # load_scenario_file validiert strikt (extra=forbid, referenzielle Integritaet);
    # ein Fehler wuerde hier als Exception hochkommen.
    scenarios = _load_all()
    assert set(scenarios) == set(EXPECTED_MACHINES)
    for external_id, scenario in scenarios.items():
        assert scenario.machine.machine_class == EXPECTED_MACHINES[external_id]
        # Park-Invariante: gemeinsame Linie ueber alle Dateien.
        assert scenario.line.label == PARK_LINE_LABEL
        # ground_truth ist vorhanden und parsebar (drift_present ist Pflichtfeld).
        assert scenario.ground_truth is not None
        assert isinstance(scenario.ground_truth.drift_present, bool)
        assert scenario.ground_truth.expected_false_alarms == 0


def test_klassen_verteilung_des_parks() -> None:
    scenarios = _load_all()
    classes = sorted(s.machine.machine_class or "" for s in scenarios.values())
    assert classes == sorted(
        ["feeder"] * 2 + ["servo_press"] * 3 + ["servo_axis"] * 4 + ["robot"] * 2 + ["vision"] * 1
    )


def test_drift_und_gesund_aufteilung() -> None:
    scenarios = _load_all()
    drift = {ext for ext, s in scenarios.items() if _gt(s).drift_present}
    assert drift == DRIFT_MACHINES
    assert set(scenarios) - drift == HEALTHY_MACHINES


@pytest.mark.parametrize("external_id", sorted(HEALTHY_MACHINES))
def test_negativkontrollen_driften_nicht(external_id: str) -> None:
    # Beleg fuer expected_false_findings=0: gesunde Schwestern haben KEINEN
    # drift-Block auf irgendeinem Datenpunkt und drift_present=false.
    scenario = _load_all()[external_id]
    assert _gt(scenario).drift_present is False
    assert all(dp.drift is None for dp in scenario.data_points), (
        f"{external_id}: gesunde Schwester darf keinen drift-Block tragen"
    )


@pytest.mark.parametrize("external_id", sorted(DRIFT_MACHINES))
def test_degradations_szenarien_haben_drift_und_ground_truth(external_id: str) -> None:
    scenario = _load_all()[external_id]
    assert any(dp.drift is not None for dp in scenario.data_points), (
        f"{external_id}: Degradations-Szenario braucht mindestens einen drift-Block"
    )
    gt = _gt(scenario).model_dump()
    assert "primary_drift" in gt
    assert gt["primary_drift"].get("t_star")
    assert gt["primary_drift"].get("data_point")


def test_maintenance_causal_pflichtfelder() -> None:
    # Jede Datei mit maintenance_causal traegt pattern + expected_false_findings=0.
    by_stem = {p.stem: load_scenario_file(p) for p in park_scenario_paths()}
    for stem, expected_pattern in EXPECTED_PATTERNS.items():
        gt = _gt(by_stem[stem]).model_dump()
        assert "maintenance_causal" in gt, f"{stem}: maintenance_causal fehlt"
        mc = gt["maintenance_causal"]
        assert mc.get("pattern") == expected_pattern, (
            f"{stem}: pattern={mc.get('pattern')!r}, erwartet {expected_pattern!r}"
        )
        assert mc.get("expected_false_findings") == 0


def test_d_kette_ist_ueber_drei_dateien_gestaffelt() -> None:
    # FD-02 (Kopf) -> PR-02 (Mitte) -> VS-01 (Endpunkt), gleiche chain_id.
    scenarios = _load_all()
    head = _gt(scenarios["FD-02"]).model_dump()["chain_role"]
    middle = _gt(scenarios["PR-02"]).model_dump()["chain_role"]
    tail = _gt(scenarios["VS-01"]).model_dump()["chain_role"]
    assert head["position"] == "head"
    assert middle["position"] == "middle"
    assert tail["position"] == "tail"
    chain_ids = {head["chain_id"], middle["chain_id"], tail["chain_id"]}
    assert chain_ids == {"underfill_chain"}
    assert tail.get("anchor") is True


def test_failure_anker_nur_bei_echten_komponenten_ausfaellen() -> None:
    # Klare Komponentenausfaelle tragen einen failure-Anker (F-PRED); der
    # Ketten-Endpunkt VS-01 (gesunde Anlage, Wirkung) und gesunde Schwestern nicht.
    scenarios = _load_all()
    with_failure = {ext for ext, s in scenarios.items() if _gt(s).failure is not None}
    assert with_failure == {"PR-01", "PR-02", "AX-02", "AX-03"}


def test_szenarien_doc_deckt_park_und_muster_ab() -> None:
    assert SZENARIEN_DOC.exists(), f"{SZENARIEN_DOC} fehlt"
    text = SZENARIEN_DOC.read_text(encoding="utf-8")
    assert PARK_LINE_LABEL in text
    # Alle Maschinen im Master-Ueberblick referenziert.
    for external_id in EXPECTED_MACHINES:
        assert external_id in text, f"szenarien.md erwaehnt {external_id} nicht"
    # Degradationsfamilien B1-B7 und Kausalmuster P1-P4 dokumentiert.
    for family in ("B1", "B2", "B3", "B4", "B5", "B6", "B7"):
        assert family in text, f"szenarien.md erwaehnt {family} nicht"
    for pattern in ("P1", "P2", "P3", "P4"):
        assert pattern in text, f"szenarien.md erwaehnt {pattern} nicht"
    # P5 ist NICHT Teil dieses PR (E1) — darf nicht als umgesetzt behauptet werden.
    assert "P5" in text  # als ausdruecklich NICHT umgesetzt erwaehnt
