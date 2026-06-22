// ============================================================
//  FOREMAN Frontend — lib/platform/roles.test.ts
//  Zweck: Sichert den Rollen-Split der Sektion I: Manager voll (Topologie + Audit
//         + Audit-Details); Schichtleiter NUR Topologie (kein Audit → der FE ruft
//         /api/v1/audit für ihn nicht auf); Werker/Techniker alles aus (default-deny).
// ============================================================
import { describe, expect, it } from "vitest";
import { platformRoleView } from "./roles";

describe("platformRoleView", () => {
  it("Manager: volle Sicht inkl. Audit-Trail und Audit-Details", () => {
    const view = platformRoleView("manager");
    expect(view.canViewTopology).toBe(true);
    expect(view.canViewAudit).toBe(true);
    expect(view.seesTopologyAuditDetail).toBe(true);
  });

  it("Schichtleiter: nur Topologie, KEIN Audit (kein Audit-Aufruf, keine Audit-Details)", () => {
    const view = platformRoleView("shift_lead");
    expect(view.canViewTopology).toBe(true);
    expect(view.canViewAudit).toBe(false);
    expect(view.seesTopologyAuditDetail).toBe(false);
  });

  it("Werker und Techniker: kein Zugang zu irgendetwas (Spiegel des Server-Guards)", () => {
    for (const role of ["worker", "technician"] as const) {
      const view = platformRoleView(role);
      expect(view.canViewTopology).toBe(false);
      expect(view.canViewAudit).toBe(false);
    }
  });
});
