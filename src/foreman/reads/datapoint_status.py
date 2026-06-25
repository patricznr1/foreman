# ============================================================
#  FOREMAN — reads/datapoint_status.py
#  Zweck: Ehrliche Status-Ableitung JE DATENPUNKT für die lebende Maschinenkarte
#         (F5 — kanonische Karte). Liefert pro Datenpunkt einen Status, der NUR aus
#         bestehenden Signalen stammt — kein neu erfundener Schwellwert
#         (Ehrlichkeitslinie, §20.5/§21.11):
#           1. offener, nicht quittierter Drift-Alarm auf dem Datenpunkt → Verdikt
#              `drift_alarm` (deckt sich mit dem Maschinen-Status drift_active),
#           2. sonst ein anderer offener Alarm auf dem Datenpunkt → `alarm`,
#           3. sonst, mit aktuellem Wert: der Eigenprofil-Korridor des Detektors
#              (median +/- effect_size_k * noise_sigma, via `corridor_at`) — innen
#              `ok`, außen `out_of_band` (Beobachtung, kein Alarm, wie der Chart-
#              Drift-Akzent),
#           4. ohne Profil: das statische, SPS-/Seed-deklarierte Normalband
#              (normal_min/normal_max) — außen `out_of_spec`,
#           5. ohne jede Bewertungsbasis: `unknown` (nie grün geraten).
#  Architektur-Einordnung: Read-Core (Schicht 2). Reine Funktion, ohne DB/ORM
#         testbar — den Korridor liefert der Aufrufer vorberechnet (`corridor_at`),
#         damit die EINE Detektor-Band-Quelle nicht dupliziert wird.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from typing import Literal

# Ehrliche Status-Stufen je Datenpunkt. Verdikt-Stufen (drift_alarm/alarm) stammen
# aus gemeldeten Alarmen; Beobachtungs-Stufen (out_of_band/out_of_spec) aus dem Wert
# gegen ein bestehendes Band; `unknown` heißt: keine ehrliche Aussage möglich.
DataPointStatus = Literal[
    "ok",
    "out_of_band",
    "out_of_spec",
    "drift_alarm",
    "alarm",
    "unknown",
]


def derive_datapoint_status(
    *,
    last_value: float | None,
    normal_min: float | None,
    normal_max: float | None,
    corridor: tuple[float, float, float] | None,
    has_open_drift_alarm: bool,
    has_open_alarm: bool,
) -> DataPointStatus:
    """Leitet den ehrlichen Datenpunkt-Status aus bestehenden Signalen ab.

    `corridor` ist der vorberechnete Eigenprofil-Korridor `(lower, mid, upper)` zum
    Zeitpunkt des letzten Werts (aus `reasoners.drift.baseline.corridor_at`) oder
    None, wenn kein/zu junges Profil vorliegt. Priorität: gemeldeter Detektor-Verdikt
    (Alarm) vor Wert-Beobachtung; Detektor-Band vor statischem Normalband; ohne
    Bewertungsbasis `unknown` statt geratenem `ok`.
    """
    # 1. Gemeldeter Detektor-Verdikt hat Vorrang vor jeder Wert-Beobachtung.
    if has_open_drift_alarm:
        return "drift_alarm"
    if has_open_alarm:
        return "alarm"
    # 2. Ohne aktuellen Wert ist keine ehrliche Beobachtung möglich.
    if last_value is None:
        return "unknown"
    # 3. Detektor-Band (Eigenprofil-Korridor) bevorzugt — Beobachtung, kein Alarm.
    if corridor is not None:
        lower, _mid, upper = corridor
        return "ok" if lower <= last_value <= upper else "out_of_band"
    # 4. Fallback: statisches, deklariertes Normalband.
    if normal_min is not None or normal_max is not None:
        if normal_min is not None and last_value < normal_min:
            return "out_of_spec"
        if normal_max is not None and last_value > normal_max:
            return "out_of_spec"
        return "ok"
    # 5. Wert vorhanden, aber keine Bewertungsbasis → ehrlich unbekannt.
    return "unknown"
