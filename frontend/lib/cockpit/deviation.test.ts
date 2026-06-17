// ============================================================
//  FOREMAN Frontend — lib/cockpit/deviation.test.ts
//  Zweck: Sichert die ehrliche Zell-Kodierung aus dem realen /overview-Vertrag:
//         Abweichungs-Intensität als 1:1-Ladder über die 5-stufige Severity,
//         Drift-Floor, kritische Zähler, Schraffur-Richtung, FCSM-Symbol.
// ============================================================
import { describe, expect, it } from "vitest";

import type { MachineStatusOut } from "@/lib/api/contracts";

import { cellKind, criticalCount, deviationLevel, toHeatmapCell } from "./deviation";

function machine(over: Partial<MachineStatusOut> = {}): MachineStatusOut {
  return {
    id: 1,
    label: "Presse 1",
    line_id: 1,
    machine_class: "Presse",
    status: "healthy",
    open_alarm_count: 0,
    open_by_severity: {},
    last_alarm_at: null,
    ...over,
  };
}

describe("deviationLevel", () => {
  it("Normalbetrieb ohne Alarme → Stufe 0 (ruhige Grundfläche)", () => {
    expect(deviationLevel(machine())).toBe(0);
  });

  it("bildet die 5-stufige Severity als Ladder ab (info→1 … emergency→5)", () => {
    expect(deviationLevel(machine({ status: "open_warning", open_alarm_count: 1, open_by_severity: { info: 1 } }))).toBe(1);
    expect(deviationLevel(machine({ status: "open_warning", open_alarm_count: 1, open_by_severity: { warning: 1 } }))).toBe(2);
    expect(deviationLevel(machine({ status: "open_warning", open_alarm_count: 1, open_by_severity: { alarm: 1 } }))).toBe(3);
    expect(deviationLevel(machine({ status: "open_warning", open_alarm_count: 1, open_by_severity: { critical: 1 } }))).toBe(4);
    expect(deviationLevel(machine({ status: "open_warning", open_alarm_count: 1, open_by_severity: { emergency: 1 } }))).toBe(5);
  });

  it("nimmt die höchste vorhandene Severity", () => {
    expect(
      deviationLevel(machine({ status: "open_warning", open_alarm_count: 3, open_by_severity: { info: 2, critical: 1 } })),
    ).toBe(4);
  });

  it("drift_active hat mindestens Stufe 2, auch bei weicher Drift-Warnung", () => {
    expect(deviationLevel(machine({ status: "drift_active", open_alarm_count: 1, open_by_severity: { info: 1 } }))).toBe(2);
  });

  it("offene Alarme ohne erkannte Severity → mindestens Stufe 1", () => {
    expect(deviationLevel(machine({ status: "open_warning", open_alarm_count: 1, open_by_severity: {} }))).toBe(1);
  });
});

describe("criticalCount", () => {
  it("summiert kritische + Notfall-Alarme", () => {
    expect(criticalCount(machine({ open_by_severity: { critical: 2, emergency: 1, warning: 5 } }))).toBe(3);
  });

  it("ist 0 ohne kritische/Notfall-Alarme", () => {
    expect(criticalCount(machine({ open_by_severity: { warning: 4 } }))).toBe(0);
  });
});

describe("cellKind", () => {
  it("kodiert Drift, offene Warnung und Normalbetrieb farbunabhängig", () => {
    expect(cellKind(machine({ status: "drift_active" }))).toBe("drift");
    expect(cellKind(machine({ status: "open_warning" }))).toBe("warning");
    expect(cellKind(machine({ status: "healthy" }))).toBe("healthy");
  });
});

describe("toHeatmapCell", () => {
  it("trägt FCSM-Symbol (komponierter Status → NE 107) und alle Kanäle", () => {
    const cell = toHeatmapCell(
      machine({ id: 7, status: "drift_active", open_alarm_count: 2, open_by_severity: { critical: 1, warning: 1 } }),
    );
    expect(cell.machineId).toBe(7);
    expect(cell.fcsm).toBe("outofspec"); // drift_active → S (Hallensprache-Mapping)
    expect(cell.kind).toBe("drift");
    expect(cell.criticalCount).toBe(1);
    expect(cell.level).toBe(4); // höchste Severity = critical
  });
});
