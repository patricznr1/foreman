// ============================================================
//  FOREMAN Frontend — lib/alarms/group.ts
//  Zweck: Gruppierung der (bereits sortierten) Liste nach Priorität / Bereich /
//         Maschine (Studie §4C: „Gruppierung wahlweise"). Erhält die globale
//         Dringlichkeits-Ordnung INNERHALB jeder Gruppe; Gruppen-Reihenfolge folgt
//         der dringlichsten enthaltenen Priorität (bei Maschine/Bereich).
//  Architektur-Einordnung: Reine Ableitung (Schicht 2). Ohne UI testbar.
// ============================================================
import { PRIORITY_LABEL, PRIORITY_ORDER, priorityRank } from "./priority";
import type { AlarmViewModel, GroupMode, Priority } from "./types";

export interface AlarmGroup {
  key: string;
  label: string;
  /** Farbgebende Priorität der Gruppe (Priorität-Modus: das Tier; sonst: dringlichste). */
  priority: Priority | null;
  rows: AlarmViewModel[];
}

function worstPriority(rows: readonly AlarmViewModel[]): Priority | null {
  let worst: Priority | null = null;
  for (const vm of rows) {
    if (worst === null || priorityRank(vm.priority) < priorityRank(worst)) {
      worst = vm.priority;
    }
  }
  return worst;
}

function groupByPriority(vms: readonly AlarmViewModel[]): AlarmGroup[] {
  const buckets = new Map<Priority, AlarmViewModel[]>();
  for (const vm of vms) {
    const list = buckets.get(vm.priority);
    if (list) {
      list.push(vm);
    } else {
      buckets.set(vm.priority, [vm]);
    }
  }
  const groups: AlarmGroup[] = [];
  for (const priority of PRIORITY_ORDER) {
    const rows = buckets.get(priority);
    if (rows && rows.length > 0) {
      groups.push({ key: `priority:${priority}`, label: PRIORITY_LABEL[priority], priority, rows });
    }
  }
  return groups;
}

/** Buckets in Erstsicht-Reihenfolge (= globale Dringlichkeit, da Eingabe sortiert). */
function groupByKey(
  vms: readonly AlarmViewModel[],
  keyOf: (vm: AlarmViewModel) => string,
  labelOf: (vm: AlarmViewModel) => string,
  prefix: string,
): AlarmGroup[] {
  const buckets = new Map<string, AlarmViewModel[]>();
  const labels = new Map<string, string>();
  for (const vm of vms) {
    const key = keyOf(vm);
    const list = buckets.get(key);
    if (list) {
      list.push(vm);
    } else {
      buckets.set(key, [vm]);
      labels.set(key, labelOf(vm));
    }
  }
  const groups: AlarmGroup[] = [];
  for (const [key, rows] of buckets) {
    groups.push({
      key: `${prefix}:${key}`,
      label: labels.get(key) ?? key,
      priority: worstPriority(rows),
      rows,
    });
  }
  return groups;
}

export function groupAlarms(vms: readonly AlarmViewModel[], mode: GroupMode): AlarmGroup[] {
  switch (mode) {
    case "priority":
      return groupByPriority(vms);
    case "machine":
      return groupByKey(
        vms,
        (vm) => String(vm.machineId),
        (vm) => vm.machineLabel,
        "machine",
      );
    case "area":
      return groupByKey(
        vms,
        (vm) => (vm.lineId === null ? "none" : String(vm.lineId)),
        (vm) => vm.lineLabel ?? "Ohne Linie",
        "area",
      );
  }
}
