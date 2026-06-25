# ============================================================
#  FOREMAN — reads/status.py
#  Zweck: Die kanonische Maschinen-Status-Komposition des Read-Cores. Eine
#         reine Funktion, die aus den offenen Alarmen einer Maschine den
#         aggregierten Gesundheitszustand ableitet — geteilt von MCP (F7),
#         den HTTP-Read-Routen und dem WebSocket-Push-Layer (F5).
#  Architektur-Einordnung: Read-Core (Schicht 2). Transport-neutral, rein,
#         ohne Session — direkt unit-testbar.
#  Hinweis: `MachineStatus` ist der kanonische Außen-/Innen-Wertebereich; die
#         MCP-Schemas referenzieren ihn, statt ihn zu duplizieren.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from foreman.db.models import Alarm
from foreman.reasoners.drift.service import DRIFT_ALARM_CODE

# Aggregierter Gesundheitszustand einer Maschine, komponiert aus offenen Warnungen.
# `critical` ist der dringlichste Zustand (FE-Mapping → FCSM „failure"/rot).
MachineStatus = Literal["healthy", "drift_active", "open_warning", "critical"]

# ISA-18.2-Severities, die den Leitstatus auf `critical` (rot) heben.
CRITICAL_SEVERITIES = frozenset({"critical", "emergency"})


def compose_status(open_alarm_list: Sequence[Alarm]) -> tuple[MachineStatus, int]:
    """Komponiert den Maschinen-Status aus den offenen Alarmen.

    Präzedenz (dringlichste zuerst): `critical` bei einem offenen Alarm
    kritischer/Notfall-Severity; sonst `drift_active` bei einer offenen, noch
    nicht quittierten Drift-Warnung; sonst `open_warning` bei irgendeinem offenen
    Alarm; sonst `healthy`.
    """
    if not open_alarm_list:
        return "healthy", 0
    has_critical = any(alarm.severity in CRITICAL_SEVERITIES for alarm in open_alarm_list)
    if has_critical:
        return "critical", len(open_alarm_list)
    unhandled_drift = any(
        alarm.code == DRIFT_ALARM_CODE and alarm.acknowledged_at is None
        for alarm in open_alarm_list
    )
    status: MachineStatus = "drift_active" if unhandled_drift else "open_warning"
    return status, len(open_alarm_list)
