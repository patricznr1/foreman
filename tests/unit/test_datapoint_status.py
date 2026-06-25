# ============================================================
#  FOREMAN — tests/unit/test_datapoint_status.py
#  Zweck: Pure-Unit-Tests für die Datenpunkt-Status-Ableitung der lebenden
#         Maschinenkarte (reads/datapoint_status.derive_datapoint_status).
#         Ehrlichkeitslinie: KEIN neu erfundener Schwellwert — Priorität
#         Alarm-Verdikt > Eigenprofil-Korridor (Detektor-Band, Beobachtung) >
#         statisches Normalband > ehrlich `unknown`.
#  Architektur-Einordnung: Read-Core (Schicht 2), ohne DB/ORM testbar.
# ============================================================
from __future__ import annotations

from foreman.reads.datapoint_status import derive_datapoint_status

# Korridor [124, 130, 136] (mid 130, Halbbreite 6) — wie corridor_at ihn liefert.
_BAND = (124.0, 130.0, 136.0)


def test_open_drift_alarm_yields_drift_alarm_even_inside_band() -> None:
    # Der gemeldete Detektor-Verdikt hat Vorrang vor jeder Wert-Beobachtung.
    status = derive_datapoint_status(
        last_value=130.0,
        normal_min=None,
        normal_max=None,
        corridor=_BAND,
        has_open_drift_alarm=True,
        has_open_alarm=True,
    )
    assert status == "drift_alarm"


def test_open_non_drift_alarm_yields_alarm() -> None:
    status = derive_datapoint_status(
        last_value=130.0,
        normal_min=None,
        normal_max=None,
        corridor=_BAND,
        has_open_drift_alarm=False,
        has_open_alarm=True,
    )
    assert status == "alarm"


def test_missing_value_yields_unknown() -> None:
    status = derive_datapoint_status(
        last_value=None,
        normal_min=120.0,
        normal_max=140.0,
        corridor=_BAND,
        has_open_drift_alarm=False,
        has_open_alarm=False,
    )
    assert status == "unknown"


def test_value_inside_corridor_is_ok() -> None:
    status = derive_datapoint_status(
        last_value=131.0,
        normal_min=None,
        normal_max=None,
        corridor=_BAND,
        has_open_drift_alarm=False,
        has_open_alarm=False,
    )
    assert status == "ok"


def test_value_outside_corridor_is_out_of_band() -> None:
    # 150 > upper(136) → außerhalb des Detektor-Korridors (Beobachtung, kein Alarm).
    status = derive_datapoint_status(
        last_value=150.0,
        normal_min=None,
        normal_max=None,
        corridor=_BAND,
        has_open_drift_alarm=False,
        has_open_alarm=False,
    )
    assert status == "out_of_band"


def test_corridor_takes_priority_over_static_band() -> None:
    # Wert im Korridor (ok), läge aber außerhalb des statischen Normalbands —
    # das Detektor-Band gewinnt, der statische Bereich wird gar nicht geprüft.
    status = derive_datapoint_status(
        last_value=131.0,
        normal_min=0.0,
        normal_max=100.0,
        corridor=_BAND,
        has_open_drift_alarm=False,
        has_open_alarm=False,
    )
    assert status == "ok"


def test_no_corridor_falls_back_to_static_band_out_of_spec() -> None:
    # Kein Eigenprofil → statisches Normalband; 150 > normal_max(140) → out_of_spec.
    status = derive_datapoint_status(
        last_value=150.0,
        normal_min=120.0,
        normal_max=140.0,
        corridor=None,
        has_open_drift_alarm=False,
        has_open_alarm=False,
    )
    assert status == "out_of_spec"


def test_no_corridor_inside_static_band_is_ok() -> None:
    status = derive_datapoint_status(
        last_value=130.0,
        normal_min=120.0,
        normal_max=140.0,
        corridor=None,
        has_open_drift_alarm=False,
        has_open_alarm=False,
    )
    assert status == "ok"


def test_value_but_no_basis_yields_unknown() -> None:
    # Wert vorhanden, aber weder Korridor noch Normalband → ehrlich unbekannt,
    # niemals grün geraten.
    status = derive_datapoint_status(
        last_value=42.0,
        normal_min=None,
        normal_max=None,
        corridor=None,
        has_open_drift_alarm=False,
        has_open_alarm=False,
    )
    assert status == "unknown"
