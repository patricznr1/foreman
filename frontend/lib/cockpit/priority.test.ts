// ============================================================
//  FOREMAN Frontend — lib/cockpit/priority.test.ts
//  Zweck: Sichert die „braucht Blick jetzt"-Spalte: Dringlichkeits-Ordnung und die
//         REALEN Querlink-Ziele (kritisch → C, Drift → E, sonst → B).
// ============================================================
import { describe, expect, it } from "vitest";

import type { MachineStatusOut } from "@/lib/api/contracts";

import { buildPriorityEntries } from "./priority";

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

describe("buildPriorityEntries", () => {
  it("schließt Maschinen im Normalbetrieb aus (nur Abweichendes)", () => {
    const entries = buildPriorityEntries([machine({ id: 1, status: "healthy" })]);
    expect(entries).toHaveLength(0);
  });

  it("ordnet kritische Alarme zuerst, dann Intensität", () => {
    const entries = buildPriorityEntries([
      machine({ id: 1, status: "open_warning", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
      machine({ id: 2, status: "open_warning", open_alarm_count: 1, open_by_severity: { critical: 1 } }),
    ]);
    expect(entries[0]!.machineId).toBe(2); // kritisch zuerst
    expect(entries[0]!.target).toBe("alarms");
    expect(entries[0]!.href).toBe("/alarms");
  });

  it("Drift ohne kritischen Alarm → Ausfallvorhersage (E)", () => {
    const entries = buildPriorityEntries([
      machine({ id: 5, status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
    ]);
    expect(entries[0]!.target).toBe("prediction");
    expect(entries[0]!.href).toBe("/insights/prediction?machine=5");
    expect(entries[0]!.reason).toBe("Abweichung erkannt");
  });

  it("offene Warnung ohne Drift/kritisch → Maschinen-Detail (B)", () => {
    const entries = buildPriorityEntries([
      machine({ id: 8, status: "open_warning", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
    ]);
    expect(entries[0]!.target).toBe("machine");
    expect(entries[0]!.href).toBe("/machines/8");
  });

  it("kappt auf die Obergrenze (3–5 dringendste)", () => {
    const many = Array.from({ length: 8 }, (_, i) =>
      machine({ id: i + 1, status: "open_warning", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
    );
    expect(buildPriorityEntries(many, 5)).toHaveLength(5);
  });
});
