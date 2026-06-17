// ============================================================
//  FOREMAN Frontend — lib/alarms/flood.ts
//  Zweck: Flood-Schutz (Studie §4C). Alarmlawinen einer vermuteten gemeinsamen
//         Quelle (Linie + Code) werden gebündelt dargestellt („12 Alarme ·
//         gemeinsame Quelle Linie 3") statt als N Einzelzeilen — sonst kippt die
//         Liste in Unlesbarkeit. Heuristisch: das Backend hat KEIN Korrelations-
//         Feld → Bündelung über (Linie, Code) der AKTIVEN Alarme (markierter
//         Anschlusspunkt für eine echte Wurzelursachen-ID). Reihenfolge bleibt
//         erhalten; das Bündel sitzt an der Stelle seines dringlichsten Mitglieds.
//  Architektur-Einordnung: Reine Ableitung (Schicht 2). Ohne UI testbar.
// ============================================================
import type { AlarmBundle, AlarmListItem, AlarmViewModel } from "./types";

export interface FloodOptions {
  /** Ab wie vielen gleichquelligen aktiven Alarmen gebündelt wird (Default 3). */
  threshold?: number;
}

function bundleKey(vm: AlarmViewModel): string {
  const line = vm.lineId === null ? "none" : String(vm.lineId);
  const code = vm.code ?? "none";
  return `${line}|${code}`;
}

function sourceLabel(representative: AlarmViewModel): string {
  if (representative.lineId !== null) {
    return `gemeinsame Quelle Linie ${representative.lineId}`;
  }
  return `gemeinsame Quelle ${representative.machineLabel}`;
}

/**
 * Bündelt gleichquellige AKTIVE Alarme einer (bereits sortierten) Zeilenmenge.
 * Quittierte/geklärte/zurückgestellte Alarme bündeln nie (sie sind in Bearbeitung).
 */
export function bundleRows(
  rows: readonly AlarmViewModel[],
  options: FloodOptions = {},
): AlarmListItem[] {
  const threshold = options.threshold ?? 3;

  // 1. aktive Zeilen nach Quelle zählen.
  const groups = new Map<string, AlarmViewModel[]>();
  for (const vm of rows) {
    if (vm.lifecycle !== "active") {
      continue;
    }
    const key = bundleKey(vm);
    const list = groups.get(key);
    if (list) {
      list.push(vm);
    } else {
      groups.set(key, [vm]);
    }
  }

  const floodedKeys = new Set<string>();
  for (const [key, members] of groups) {
    if (members.length >= threshold) {
      floodedKeys.add(key);
    }
  }

  // 2. in Originalreihenfolge ausgeben; ein Flood-Bündel ersetzt seine Mitglieder
  //    an der Position des ersten (dringlichsten) Mitglieds.
  const emitted = new Set<string>();
  const items: AlarmListItem[] = [];
  for (const vm of rows) {
    if (vm.lifecycle === "active") {
      const key = bundleKey(vm);
      if (floodedKeys.has(key)) {
        if (!emitted.has(key)) {
          emitted.add(key);
          const members = groups.get(key) ?? [vm];
          const representative = members[0] ?? vm;
          const bundle: AlarmBundle = {
            key,
            lineId: representative.lineId,
            sourceLabel: sourceLabel(representative),
            code: representative.code,
            count: members.length,
            priority: representative.priority,
            members,
            representative,
            // Der Unquittiert-Puls überlebt die Bündelung (ISA-18.2-konform).
            hasActiveCriticalPulse: members.some((member) => member.pulse),
          };
          items.push({ kind: "bundle", bundle });
        }
        continue;
      }
    }
    items.push({ kind: "row", row: vm });
  }

  return items;
}
