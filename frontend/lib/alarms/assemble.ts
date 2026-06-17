// ============================================================
//  FOREMAN Frontend — lib/alarms/assemble.ts
//  Zweck: Die reine Assemblierungs-Pipeline der Alarm-Sicht: rohe AlarmRead[] →
//         View-Modelle → Scope-Filter → Zähler → UI-Filter → Sortierung →
//         Gruppierung → Flood-Bündelung → flache, virtualisierbare VisualRow-Folge.
//         EIN Ein-/Ausgang, deterministisch, vollständig ohne UI/Transport testbar
//         (Studie §5.1: abgeleiteter View-State liest nur, kennt keinen Transport).
//  Architektur-Einordnung: Reine Ableitung (Schicht 2, Pipeline). Ohne UI testbar.
// ============================================================
import type { AlarmRead } from "@/lib/api/contracts";
import { countByPriority, countDrift } from "./counts";
import { bundleRows } from "./flood";
import { groupAlarms } from "./group";
import { sortAlarms } from "./sort";
import type {
  AlarmFilter,
  AlarmView,
  AlarmViewModel,
  GroupMode,
  MachineMeta,
  PriorityCounts,
  VisualRow,
} from "./types";
import { type BuildContext, buildAlarmViewModel } from "./view-model";

export interface AssembleOptions {
  machines: ReadonlyMap<number, MachineMeta>;
  shelf: ReadonlyMap<number, number>;
  now: number;
  newIds: ReadonlySet<number>;
  filter: AlarmFilter;
  groupMode: GroupMode;
  expandedBundles: ReadonlySet<string>;
  /** Flood-Schwelle (Default 3). */
  floodThreshold?: number;
  /** Scope-Filter (UX): nur sichtbare Maschinen. Ohne → alles sichtbar. */
  visibleMachine?: (machineId: number, lineId: number | null) => boolean;
  /** Live-Zähler aus dem overview-Aggregat (überschreibt die Zeilen-Zählung im Kopf). */
  liveCounts?: PriorityCounts;
}

/** Default-Filter: offene Alarme, alle Prioritäten, inkl. Drift. */
export function defaultFilter(): AlarmFilter {
  return { priorities: new Set(), driftOnly: false, lifecycle: "open" };
}

function passesFilter(
  vm: Pick<AlarmViewModel, "priority" | "isDrift" | "lifecycle">,
  filter: AlarmFilter,
): boolean {
  if (filter.driftOnly && !vm.isDrift) {
    return false;
  }
  if (filter.priorities.size > 0 && !filter.priorities.has(vm.priority)) {
    return false;
  }
  switch (filter.lifecycle) {
    case "open":
      return vm.lifecycle !== "cleared";
    case "acknowledged":
      return vm.lifecycle === "acknowledged";
    case "cleared":
      return vm.lifecycle === "cleared";
    case "all":
      return true;
  }
}

export function assembleAlarmView(
  alarms: readonly AlarmRead[],
  options: AssembleOptions,
): AlarmView {
  const buildCtx: BuildContext = {
    machines: options.machines,
    shelf: options.shelf,
    now: options.now,
    newIds: options.newIds,
  };

  let vms = alarms.map((alarm) => buildAlarmViewModel(alarm, buildCtx));

  if (options.visibleMachine) {
    const visible = options.visibleMachine;
    vms = vms.filter((vm) => visible(vm.machineId, vm.lineId));
  }

  // Zähler über das volle (scope-gefilterte) Bild — der Kopf zeigt die wahre Lage,
  // nicht nur die gerade gefilterte Teilmenge.
  const counts = options.liveCounts ?? countByPriority(vms);
  const driftCount = countDrift(vms);

  const filtered = vms.filter((vm) => passesFilter(vm, options.filter));
  const sorted = sortAlarms(filtered);
  const groups = groupAlarms(sorted, options.groupMode);

  const rows: VisualRow[] = [];
  let total = 0;
  const threshold = options.floodThreshold ?? 3;

  for (const group of groups) {
    rows.push({
      kind: "header",
      id: `h:${group.key}`,
      label: group.label,
      count: group.rows.length,
      priority: group.priority,
    });
    const items = bundleRows(group.rows, { threshold });
    for (const item of items) {
      if (item.kind === "row") {
        rows.push({ kind: "row", id: `r:${item.row.id}`, row: item.row });
        total += 1;
      } else {
        rows.push({ kind: "bundle", id: `b:${item.bundle.key}`, bundle: item.bundle });
        total += item.bundle.count;
        if (options.expandedBundles.has(item.bundle.key)) {
          for (const member of item.bundle.members) {
            rows.push({ kind: "row", id: `r:${member.id}`, row: member });
          }
        }
      }
    }
  }

  return { rows, counts, driftCount, total };
}

export const GROUP_MODES: readonly GroupMode[] = ["priority", "area", "machine"] as const;
