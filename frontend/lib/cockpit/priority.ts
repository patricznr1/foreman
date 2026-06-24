// ============================================================
//  FOREMAN Frontend — lib/cockpit/priority.ts
//  Zweck: Die rechte „braucht Blick jetzt"-Spalte (§4A): die 3–5 dringendsten
//         Einstiege, nach Dringlichkeit geordnet (ISA-18.2-Priorisierung). Jeder
//         Eintrag trägt sein REALES Querlink-Ziel: kritische Alarme/Warnungen → B
//         (Maschine, Alarm im Kontext: Trend, Komponenten, offene Alarme), Drift → E
//         (Ausfallrisiko). HITL: nur Navigation, keine Aktorik.
//  Architektur-Einordnung: View-State (Schicht 2, rein, testbar).
// ============================================================
import type { MachineStatusOut } from "@/lib/api/contracts";
import type { Fcsm } from "@/lib/ui/wording";

import { toHeatmapCell } from "./deviation";
import type { CellKind, DeviationLevel } from "./types";
import { machineHref, predictionHref } from "./url";

/** Höchstens so viele Einstiege (Studie §4A: 3–5 dringendste). */
export const PRIORITY_MAX = 5;

export type PriorityTarget = "alarms" | "prediction" | "machine";

export interface PriorityEntry {
  machineId: number;
  label: string;
  machineClass: string | null;
  fcsm: Fcsm;
  kind: CellKind;
  level: DeviationLevel;
  criticalCount: number;
  openAlarmCount: number;
  /** Kurzbegründung in Hallensprache (warum dieser Einstieg jetzt zählt). */
  reason: string;
  target: PriorityTarget;
  href: string;
}

/** Drift vor offener Warnung (gleiche Severity) — die Anbahnung zählt zuerst. */
const KIND_RANK: Record<CellKind, number> = { drift: 0, warning: 1, healthy: 2 };

function reasonFor(criticalOpen: number, kind: CellKind, openAlarmCount: number): string {
  if (criticalOpen > 0) {
    return `${criticalOpen} offene${criticalOpen === 1 ? "r kritischer Alarm" : " kritische Alarme"}`;
  }
  if (kind === "drift") {
    return "Abweichung erkannt";
  }
  if (openAlarmCount > 0) {
    return `${openAlarmCount} offene${openAlarmCount === 1 ? "r Alarm" : " Alarme"}`;
  }
  return "Offene Warnung";
}

/**
 * Ordnet die abweichenden Maschinen nach Dringlichkeit und liefert die dringendsten
 * Einstiege mit ihrem realen Querlink-Ziel. Reihenfolge: kritische Alarme zuerst,
 * dann Abweichungs-Intensität, dann Anbahnung (Drift) vor offener Warnung, dann
 * mehr offene Alarme, dann stabil nach Maschinen-ID.
 */
export function buildPriorityEntries(
  machines: MachineStatusOut[],
  max: number = PRIORITY_MAX,
): PriorityEntry[] {
  const candidates = machines
    .map((machine) => toHeatmapCell(machine))
    .filter((cell) => cell.level > 0);

  candidates.sort((a, b) => {
    if (b.criticalCount !== a.criticalCount) {
      return b.criticalCount - a.criticalCount;
    }
    if (b.level !== a.level) {
      return b.level - a.level;
    }
    if (KIND_RANK[a.kind] !== KIND_RANK[b.kind]) {
      return KIND_RANK[a.kind] - KIND_RANK[b.kind];
    }
    if (b.openAlarmCount !== a.openAlarmCount) {
      return b.openAlarmCount - a.openAlarmCount;
    }
    return a.machineId - b.machineId;
  });

  return candidates.slice(0, max).map((cell) => {
    let target: PriorityTarget;
    let href: string;
    if (cell.criticalCount > 0) {
      // Kritischer Alarm → direkt zur auslösenden Maschine (Sektion B): dort steht der
      // Alarm im Kontext (Trend, Komponenten, offene Alarme) statt in der flachen Liste.
      target = "machine";
      href = machineHref(cell.machineId);
    } else if (cell.kind === "drift") {
      target = "prediction";
      href = predictionHref(cell.machineId);
    } else {
      target = "machine";
      href = machineHref(cell.machineId);
    }
    return {
      machineId: cell.machineId,
      label: cell.label,
      machineClass: cell.machineClass,
      fcsm: cell.fcsm,
      kind: cell.kind,
      level: cell.level,
      criticalCount: cell.criticalCount,
      openAlarmCount: cell.openAlarmCount,
      reason: reasonFor(cell.criticalCount, cell.kind, cell.openAlarmCount),
      target,
      href,
    };
  });
}
