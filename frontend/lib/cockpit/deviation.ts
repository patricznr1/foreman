// ============================================================
//  FOREMAN Frontend — lib/cockpit/deviation.ts
//  Zweck: Reine Ableitung der Zell-Kodierung aus dem realen /overview-Vertrag
//         (MachineStatusOut). Da das Backend (heute) KEINEN kontinuierlichen
//         Drift-Score liefert (F4-Eigenprofil reserviert/null), leitet das Cockpit
//         die Abweichungs-INTENSITÄT ehrlich aus der offenen Alarm-Severity +
//         dem komponierten Status ab — ein sauberer 1:1-Ladder über die 5-stufige
//         Backend-Severity (info→1 … emergency→5). Anschlusspunkt: sobald F4 einen
//         kontinuierlichen Drift-Score liefert, ersetzt der diese Heuristik, ohne
//         die Komponenten zu ändern (Designstudie §4A „Abweichung gegen Eigenprofil").
//  Architektur-Einordnung: View-State (Schicht 2, rein, ohne UI/Transport testbar).
//  Quelle: schemas/dashboard.py (open_by_severity), reads/status.py (compose_status).
// ============================================================
import type { MachineStatusOut } from "@/lib/api/contracts";
import { MACHINE_STATUS_TO_FCSM } from "@/lib/ui/wording";

import type { CellKind, DeviationLevel, HeatmapCell } from "./types";

/**
 * ISA-18.2-Severity → Intensitätsgewicht (1..5). Bildet die 5-stufige Backend-
 * Severity als sauberen Ladder ab; ältere/abweichende Keys werden defensiv
 * gemappt, Unbekanntes auf die niedrigste sichtbare Stufe (1).
 */
const SEVERITY_WEIGHT: Record<string, number> = {
  emergency: 5,
  critical: 4,
  alarm: 3,
  high: 3,
  warning: 2,
  medium: 2,
  low: 1,
  info: 1,
  journal: 1,
};

/** drift_active ist eine Abweichung, auch wenn die Drift-Warnung weich ist → mindestens Stufe 2. */
const DRIFT_FLOOR = 2;

/** Offene kritische + Notfall-Alarme einer Maschine (für KPI + Prioritätsspalte). */
export function criticalCount(machine: MachineStatusOut): number {
  const sev = machine.open_by_severity;
  return (sev.critical ?? 0) + (sev.emergency ?? 0);
}

/**
 * Abweichungs-Intensität 0..5: ruhig im Normalbetrieb (0 → Grundfläche), sonst die
 * höchste offene Severity. Maschinen mit offenen Alarmen ohne erkannte Severity
 * tragen mindestens Stufe 1; drift_active mindestens DRIFT_FLOOR.
 */
export function deviationLevel(machine: MachineStatusOut): DeviationLevel {
  if (machine.status === "healthy" && machine.open_alarm_count === 0) {
    return 0;
  }
  let weight = 0;
  for (const [severity, count] of Object.entries(machine.open_by_severity)) {
    if (count > 0) {
      weight = Math.max(weight, SEVERITY_WEIGHT[severity] ?? 1);
    }
  }
  if (weight === 0 && machine.open_alarm_count > 0) {
    weight = 1;
  }
  if (machine.status === "drift_active") {
    weight = Math.max(weight, DRIFT_FLOOR);
  }
  const clamped = Math.min(5, Math.max(0, weight));
  return clamped as DeviationLevel;
}

/**
 * Schraffur-/Richtungskanal: brennt (offene Warnung) vs. bahnt sich an (Drift) —
 * farbunabhängig (Pattern-Winkel + FCSM-Symbol tragen die Bedeutung mit).
 */
export function cellKind(machine: MachineStatusOut): CellKind {
  if (machine.status === "drift_active") {
    return "drift";
  }
  if (machine.status === "open_warning" || machine.status === "critical") {
    return "warning";
  }
  return "healthy";
}

/** Baut die abgeleitete Heatmap-Zelle aus einer Maschine (mehrkanalig, paraphrasiert). */
export function toHeatmapCell(machine: MachineStatusOut): HeatmapCell {
  return {
    machineId: machine.id,
    label: machine.label,
    machineClass: machine.machine_class,
    lineId: machine.line_id,
    status: machine.status,
    fcsm: MACHINE_STATUS_TO_FCSM[machine.status],
    level: deviationLevel(machine),
    kind: cellKind(machine),
    openAlarmCount: machine.open_alarm_count,
    criticalCount: criticalCount(machine),
  };
}
