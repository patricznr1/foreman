// ============================================================
//  FOREMAN Frontend — lib/alarms/counts.ts
//  Zweck: Prioritäts-Zähler für den Listenkopf („2 kritisch · 5 hoch · 11 mittel").
//         Zwei Quellen: (a) aus den geladenen Alarm-Zeilen, (b) LIVE aus dem
//         overview-Aggregat (open_by_severity) — damit der Kopf „atmet", ohne die
//         Liste neu zu laden (Ambient-Read, Studie §3.2).
//  Architektur-Einordnung: Reine Ableitung (Schicht 2). Ohne UI testbar.
// ============================================================
import type { FleetOverviewOut } from "@/lib/api/contracts";
import { severityToPriority } from "./priority";
import type { AlarmViewModel, PriorityCounts } from "./types";

export function emptyCounts(): PriorityCounts {
  return { critical: 0, high: 0, medium: 0, low: 0, journal: 0 };
}

/** Offene (nicht geklärte) Alarme je Priorität — der Leitwert des Kopfes. */
export function countByPriority(vms: readonly AlarmViewModel[]): PriorityCounts {
  const counts = emptyCounts();
  for (const vm of vms) {
    if (vm.lifecycle === "cleared") {
      continue;
    }
    counts[vm.priority] += 1;
  }
  return counts;
}

/** Offene Drift-Warnungen (eigene, klar markierte Klasse). */
export function countDrift(vms: readonly AlarmViewModel[]): number {
  let n = 0;
  for (const vm of vms) {
    if (vm.isDrift && vm.lifecycle !== "cleared") {
      n += 1;
    }
  }
  return n;
}

/**
 * Live-Zähler aus dem overview-Aggregat: summiert open_by_severity über alle
 * sichtbaren Maschinen und mappt die Backend-Severity auf die Prioritäts-Tiers.
 * Optionaler Maschinen-Filter (Scope) — nur sichtbare Maschinen zählen.
 */
export function countByPriorityFromOverview(
  overview: FleetOverviewOut,
  isVisible?: (machineId: number, lineId: number | null) => boolean,
): PriorityCounts {
  const counts = emptyCounts();
  for (const machine of overview.machines) {
    if (isVisible && !isVisible(machine.id, machine.line_id)) {
      continue;
    }
    for (const [severity, n] of Object.entries(machine.open_by_severity)) {
      counts[severityToPriority(severity)] += n;
    }
  }
  return counts;
}

/** Gibt es offene kritische Alarme? (für die globale Leisten-Verschärfung). */
export function hasCritical(counts: PriorityCounts): boolean {
  return counts.critical > 0;
}
