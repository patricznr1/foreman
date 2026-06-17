// ============================================================
//  FOREMAN Frontend — lib/cockpit/kpis.ts
//  Zweck: KPI-Aggregate des Cockpits aus dem realen /overview-Vertrag — über die
//         (scope-gefilterte) Maschinenliste gerechnet, damit die Kennzahlen dem
//         gewählten Geltungsbereich folgen (nicht das flottenweite by_status). Die
//         Werte tragen ihren Zustands-Indikator mit (KpiTile nie nackt, Prinzip 6).
//         Severity-Farbe ist hier erlaubt (KPI-Zeile, §4A) — die Heatmap-Fläche
//         bleibt severity-frei.
//  Architektur-Einordnung: View-State (Schicht 2, rein, testbar).
// ============================================================
import type { MachineStatusOut } from "@/lib/api/contracts";
import type { Fcsm } from "@/lib/ui/wording";

import { criticalCount } from "./deviation";

export interface CockpitKpis {
  total: number;
  healthy: number;
  /** Nicht im Normalbetrieb: Drift UND offene Warnungen (sonst fiele open_warning aus). */
  deviating: number;
  /** Flottenverfügbarkeit in Prozent (gerundet); leere Flotte → 100 (nichts auffällig). */
  availabilityPct: number;
  /** Maschinen mit aktiver, unquittierter Drift (by_status.drift_active im Scope). */
  driftCount: number;
  openAlarmTotal: number;
  /** Offene kritische + Notfall-Alarme (die einzige vollflächig erlaubte Severity). */
  criticalOpen: number;
}

export function buildCockpitKpis(machines: MachineStatusOut[]): CockpitKpis {
  const total = machines.length;
  let healthy = 0;
  let driftCount = 0;
  let deviating = 0;
  let openAlarmTotal = 0;
  let criticalOpen = 0;

  for (const machine of machines) {
    if (machine.status === "healthy") {
      healthy += 1;
    } else {
      deviating += 1;
    }
    if (machine.status === "drift_active") {
      driftCount += 1;
    }
    openAlarmTotal += machine.open_alarm_count;
    criticalOpen += criticalCount(machine);
  }

  const availabilityPct = total > 0 ? Math.round((healthy / total) * 100) : 100;

  return { total, healthy, deviating, availabilityPct, driftCount, openAlarmTotal, criticalOpen };
}

/** Verfügbarkeit → ruhige Zustands-Rampe: hoch ok, mittel außer Spezifikation, niedrig Funktionsprüfung. */
export function availabilityFcsm(pct: number): Fcsm {
  if (pct >= 95) {
    return "ok";
  }
  if (pct >= 80) {
    return "outofspec";
  }
  return "check";
}

/** Drift-Zähler → Zustand: keiner ok, sonst außer Spezifikation (gedämpft, kein Alarm-Rot). */
export function driftFcsm(count: number): Fcsm {
  return count > 0 ? "outofspec" : "ok";
}

/** Offene kritische Alarme → Zustand: keiner ok, sonst Ausfall (die eine dominante Severity). */
export function criticalFcsm(count: number): Fcsm {
  return count > 0 ? "failure" : "ok";
}
