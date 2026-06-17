// ============================================================
//  FOREMAN Frontend — lib/cockpit/matrix.ts
//  Zweck: Verdichtet die (scope-gefilterte) Maschinenliste zur Heatmap-Matrix —
//         Zeilen = Maschinenklassen (Kerninnovation §4A), Spalten = einzelne
//         Maschinen. STABILE Ordnung (Klassenname, dann Maschinen-ID), damit der
//         Live-Push Zellen IN-PLACE aktualisiert, ohne Zeilen/Spalten umzusortieren
//         (kein Layout-Sprung, §3.2/§5.6). Markiert systematische Drift einer Klasse.
//  Architektur-Einordnung: View-State (Schicht 2, rein, testbar).
// ============================================================
import type { MachineStatusOut } from "@/lib/api/contracts";

import { toHeatmapCell } from "./deviation";
import type { HeatmapCell, HeatmapMatrix, HeatmapRow } from "./types";

/** Schlüssel für die „ohne Klasse"-Zeile (sortiert ans Ende). */
const NO_CLASS_KEY = "￿";
const NO_CLASS_LABEL = "Ohne Klasse";

/** Ab dieser Klassen-Mindestgröße + Drift-Mehrheit gilt eine Zeile als systematisch driftend. */
const SYSTEMATIC_MIN_MACHINES = 2;
const SYSTEMATIC_DRIFT_SHARE = 0.5;

/** Sortierschlüssel einer Klasse: ohne Klasse zuletzt, sonst alphabetisch (de). */
function classSortKey(machineClass: string | null): string {
  return machineClass === null ? NO_CLASS_KEY : machineClass.toLocaleLowerCase("de-DE");
}

function buildRow(machineClass: string | null, cells: HeatmapCell[]): HeatmapRow {
  const sortedCells = [...cells].sort((a, b) => a.machineId - b.machineId);
  const deviatingCount = sortedCells.filter((cell) => cell.level > 0).length;
  const driftCount = sortedCells.filter((cell) => cell.kind === "drift").length;
  const systematic =
    sortedCells.length >= SYSTEMATIC_MIN_MACHINES &&
    driftCount / sortedCells.length >= SYSTEMATIC_DRIFT_SHARE;
  return {
    machineClass,
    label: machineClass ?? NO_CLASS_LABEL,
    cells: sortedCells,
    deviatingCount,
    systematic,
  };
}

/**
 * Baut die Heatmap-Matrix aus der Maschinenliste. Gruppiert primär nach Klasse,
 * Zeilen stabil nach Klassenname, Zellen stabil nach Maschinen-ID.
 */
export function buildHeatmapMatrix(machines: MachineStatusOut[]): HeatmapMatrix {
  const byClass = new Map<string, { machineClass: string | null; cells: HeatmapCell[] }>();
  for (const machine of machines) {
    const key = classSortKey(machine.machine_class);
    const group = byClass.get(key);
    if (group === undefined) {
      byClass.set(key, { machineClass: machine.machine_class, cells: [toHeatmapCell(machine)] });
    } else {
      group.cells.push(toHeatmapCell(machine));
    }
  }

  const rows = [...byClass.entries()]
    .sort(([a], [b]) => a.localeCompare(b, "de-DE"))
    .map(([, group]) => buildRow(group.machineClass, group.cells));

  return { rows, machineCount: machines.length };
}
