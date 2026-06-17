// ============================================================
//  FOREMAN Frontend — lib/cockpit/matrix.test.ts
//  Zweck: Sichert die Kerninnovation §4A: Gruppierung nach Klasse (Zeilen) ×
//         Maschine (Spalten), stabile Ordnung (kein Live-Sprung), sichtbares
//         systematisches Drift-Muster („diese ganze Klasse driftet").
// ============================================================
import { describe, expect, it } from "vitest";

import type { MachineStatusOut } from "@/lib/api/contracts";

import { buildHeatmapMatrix } from "./matrix";

function machine(over: Partial<MachineStatusOut> = {}): MachineStatusOut {
  return {
    id: 1,
    label: "M",
    line_id: 1,
    machine_class: "Presse",
    status: "healthy",
    open_alarm_count: 0,
    open_by_severity: {},
    last_alarm_at: null,
    ...over,
  };
}

describe("buildHeatmapMatrix", () => {
  it("gruppiert nach Maschinenklasse (Zeilen) und zählt alle Maschinen", () => {
    const matrix = buildHeatmapMatrix([
      machine({ id: 1, machine_class: "Presse" }),
      machine({ id: 2, machine_class: "Spindel" }),
      machine({ id: 3, machine_class: "Presse" }),
    ]);
    expect(matrix.machineCount).toBe(3);
    expect(matrix.rows.map((r) => r.machineClass)).toEqual(["Presse", "Spindel"]);
    expect(matrix.rows[0]!.cells).toHaveLength(2);
  });

  it("ordnet Zeilen alphabetisch und stellt die klassenlose Zeile ans Ende", () => {
    const matrix = buildHeatmapMatrix([
      machine({ id: 1, machine_class: null }),
      machine({ id: 2, machine_class: "Spindel" }),
      machine({ id: 3, machine_class: "Bohrwerk" }),
    ]);
    expect(matrix.rows.map((r) => r.label)).toEqual(["Bohrwerk", "Spindel", "Ohne Klasse"]);
  });

  it("ordnet Zellen einer Zeile stabil nach Maschinen-ID (kein Live-Sprung)", () => {
    const matrix = buildHeatmapMatrix([
      machine({ id: 9, machine_class: "Presse" }),
      machine({ id: 2, machine_class: "Presse" }),
      machine({ id: 5, machine_class: "Presse" }),
    ]);
    expect(matrix.rows[0]!.cells.map((c) => c.machineId)).toEqual([2, 5, 9]);
  });

  it("markiert systematische Drift, wenn die Mehrheit der Klasse driftet", () => {
    const matrix = buildHeatmapMatrix([
      machine({ id: 1, machine_class: "Presse", status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
      machine({ id: 2, machine_class: "Presse", status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
      machine({ id: 3, machine_class: "Presse", status: "healthy" }),
    ]);
    expect(matrix.rows[0]!.systematic).toBe(true);
    expect(matrix.rows[0]!.deviatingCount).toBe(2);
  });

  it("markiert KEINE systematische Drift bei Einzel-Maschine oder Minderheit", () => {
    const single = buildHeatmapMatrix([
      machine({ id: 1, machine_class: "Spindel", status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
    ]);
    expect(single.rows[0]!.systematic).toBe(false);

    const minority = buildHeatmapMatrix([
      machine({ id: 1, machine_class: "Presse", status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
      machine({ id: 2, machine_class: "Presse", status: "healthy" }),
      machine({ id: 3, machine_class: "Presse", status: "healthy" }),
    ]);
    expect(minority.rows[0]!.systematic).toBe(false);

    // 50/50 ist KEINE Mehrheit (strikt mehr als die Hälfte nötig).
    const half = buildHeatmapMatrix([
      machine({ id: 1, machine_class: "Presse", status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
      machine({ id: 2, machine_class: "Presse", status: "healthy" }),
    ]);
    expect(half.rows[0]!.systematic).toBe(false);
  });
});
