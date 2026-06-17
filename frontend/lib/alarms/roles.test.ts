// ============================================================
//  FOREMAN Frontend — lib/alarms/roles.test.ts
//  Zweck: Rollen-Varianten (Matrix 3.1) — Werker kein Quittieren, Manager nur
//         Aggregat, Scope-Sichtbarkeit als UX-Spiegel (default-deny bei Unbekannt).
// ============================================================
import { describe, expect, it } from "vitest";
import { alarmRoleView, canAcknowledgeAlarms, machineInScope } from "./roles";

describe("alarmRoleView — Matrix 3.1", () => {
  it("Werker: lesen+filtern, KEIN Quittieren", () => {
    expect(canAcknowledgeAlarms("worker")).toBe(false);
    expect(alarmRoleView("worker").aggregateOnly).toBe(false);
    expect(alarmRoleView("worker").scope).toBe("assigned-machines");
  });

  it("Schichtleiter: voll, Quittieren ist Default-Aktion", () => {
    expect(canAcknowledgeAlarms("shift_lead")).toBe(true);
    expect(alarmRoleView("shift_lead").acknowledgeIsDefault).toBe(true);
    expect(alarmRoleView("shift_lead").scope).toBe("own-lines");
  });

  it("Techniker: zugewiesene, darf quittieren", () => {
    expect(canAcknowledgeAlarms("technician")).toBe(true);
    expect(alarmRoleView("technician").scope).toBe("assigned-machines");
  });

  it("Manager: nur Aggregat, KEIN Einzel-Quittieren", () => {
    expect(canAcknowledgeAlarms("manager")).toBe(false);
    expect(alarmRoleView("manager").aggregateOnly).toBe(true);
  });

  it("unbekannte Rolle → restriktivste Sicht (default-deny)", () => {
    // @ts-expect-error — bewusst ungültige Rolle (offener Backend-String)
    expect(canAcknowledgeAlarms("intruder")).toBe(false);
    // @ts-expect-error — bewusst ungültige Rolle (offener Backend-String)
    expect(alarmRoleView("intruder").aggregateOnly).toBe(true);
  });
});

describe("machineInScope — UX-Filter (Server bleibt Autorität)", () => {
  const worker = { role: "worker" as const, assigned_machine_ids: [1, 5], assigned_line_ids: [] };
  const lead = { role: "shift_lead" as const, assigned_machine_ids: [], assigned_line_ids: [3] };
  const mgr = { role: "manager" as const, assigned_machine_ids: [], assigned_line_ids: [] };

  it("Werker sieht nur zugewiesene Maschinen", () => {
    expect(machineInScope(worker, 1, 3)).toBe(true);
    expect(machineInScope(worker, 2, 3)).toBe(false);
  });

  it("Schichtleiter sieht Maschinen seiner Linien", () => {
    expect(machineInScope(lead, 99, 3)).toBe(true);
    expect(machineInScope(lead, 99, 7)).toBe(false);
    expect(machineInScope(lead, 99, null)).toBe(false);
  });

  it("Manager sieht alles", () => {
    expect(machineInScope(mgr, 123, 42)).toBe(true);
  });
});
