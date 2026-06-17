// ============================================================
//  FOREMAN Frontend — lib/capture/scope.test.ts
//  Zweck: Sichert den auswählbaren-Maschinen-UX-Filter (KEINE AuthZ-Grenze).
// ============================================================
import { describe, expect, it } from "vitest";
import { isMachineSelectable, machineInScope, machineLabel, selectableMachines } from "./scope";
import { makeMachine, makeUser } from "./testing/fixtures";

describe("machineInScope", () => {
  const m = makeMachine({ id: 100, line_id: 5 });

  it("lässt manager und techniker jede Maschine wählen (unrestricted)", () => {
    expect(machineInScope(makeUser({ role: "manager" }), m)).toBe(true);
    expect(machineInScope(makeUser({ role: "technician" }), m)).toBe(true);
  });

  it("beschränkt den Werker auf seine zugewiesenen Maschinen", () => {
    expect(machineInScope(makeUser({ role: "worker", assigned_machine_ids: [100] }), m)).toBe(true);
    expect(machineInScope(makeUser({ role: "worker", assigned_machine_ids: [7] }), m)).toBe(false);
  });

  it("beschränkt den Schichtleiter auf Maschinen seiner Linien", () => {
    expect(machineInScope(makeUser({ role: "shift_lead", assigned_line_ids: [5] }), m)).toBe(true);
    expect(machineInScope(makeUser({ role: "shift_lead", assigned_line_ids: [9] }), m)).toBe(false);
  });

  it("verwehrt dem Schichtleiter Einzelmaschinen ohne Linie (line_id null)", () => {
    const solo = makeMachine({ id: 101, line_id: null });
    expect(machineInScope(makeUser({ role: "shift_lead", assigned_line_ids: [5] }), solo)).toBe(false);
  });

  it("ist default-deny für leeres Scope-Array und unbekannte Rollen", () => {
    expect(machineInScope(makeUser({ role: "worker", assigned_machine_ids: [] }), m)).toBe(false);
    expect(machineInScope(makeUser({ role: "ghost" as never }), m)).toBe(false);
  });
});

describe("selectableMachines / isMachineSelectable", () => {
  const machines = [
    makeMachine({ id: 1, line_id: 5 }),
    makeMachine({ id: 2, line_id: 6 }),
    makeMachine({ id: 3, line_id: null }),
  ];

  it("filtert die Liste auf den Scope und erhält die Reihenfolge", () => {
    const user = makeUser({ role: "worker", assigned_machine_ids: [3, 1] });
    expect(selectableMachines(user, machines).map((x) => x.id)).toEqual([1, 3]);
  });

  it("entscheidet, ob eine vorausgewählte machine_id wählbar ist (sonst keine Vorauswahl)", () => {
    const user = makeUser({ role: "worker", assigned_machine_ids: [2] });
    expect(isMachineSelectable(user, 2, machines)).toBe(true);
    expect(isMachineSelectable(user, 1, machines)).toBe(false);
    expect(isMachineSelectable(user, 999, machines)).toBe(false);
  });
});

describe("machineLabel", () => {
  it("nutzt das Label, sonst den Fallback 'Maschine {id}'", () => {
    expect(machineLabel(makeMachine({ id: 4, label: "Drehbank 4" }))).toBe("Drehbank 4");
    expect(machineLabel(makeMachine({ id: 4, label: "  " }))).toBe("Maschine 4");
  });
});
