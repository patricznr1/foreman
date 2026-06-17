// ============================================================
//  FOREMAN Frontend — lib/alarms/sort.ts
//  Zweck: Prioritäts-Staffelung der Liste (Studie §4C: „kritische immer oben",
//         nicht chronologisch-flach). Deterministische, stabile Ordnung: Tier →
//         Lebenszyklus (aktiv vor quittiert vor zurückgestellt vor geklärt) →
//         Severity-Feinrang (Notfall vor Kritisch) → Zeit (jüngste zuerst).
//  Architektur-Einordnung: Reine Ableitung (Schicht 2). Ohne UI testbar.
// ============================================================
import { priorityRank, severityRank } from "./priority";
import type { AlarmViewModel, DisplayLifecycle } from "./types";

const LIFECYCLE_WEIGHT: Record<DisplayLifecycle, number> = {
  active: 0,
  acknowledged: 1,
  shelved: 2,
  cleared: 3,
};

function raisedAtMs(value: string): number {
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? 0 : ms;
}

export function compareAlarms(a: AlarmViewModel, b: AlarmViewModel): number {
  const tier = priorityRank(a.priority) - priorityRank(b.priority);
  if (tier !== 0) {
    return tier;
  }
  const life = LIFECYCLE_WEIGHT[a.lifecycle] - LIFECYCLE_WEIGHT[b.lifecycle];
  if (life !== 0) {
    return life;
  }
  const sev = severityRank(a.severity) - severityRank(b.severity);
  if (sev !== 0) {
    return sev;
  }
  // Jüngste zuerst innerhalb gleicher Dringlichkeit (Live-Insert oben im Tier).
  const time = raisedAtMs(b.raisedAt) - raisedAtMs(a.raisedAt);
  if (time !== 0) {
    return time;
  }
  return b.id - a.id;
}

/** Stabile, deterministische Sortierung (kein In-Place auf der Eingabe). */
export function sortAlarms(vms: readonly AlarmViewModel[]): AlarmViewModel[] {
  return [...vms].sort(compareAlarms);
}
