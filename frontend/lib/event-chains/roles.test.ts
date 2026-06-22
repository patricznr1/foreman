// ============================================================
//  FOREMAN Frontend — lib/event-chains/roles.test.ts
//  Zweck: Rollen-Varianten §4D (Schichtleiter triggert+pinnt, Techniker pinnt,
//         Werker liest, Manager Aggregat) + default-deny für unbekannte Rollen.
// ============================================================
import { describe, expect, it } from "vitest";
import type { Role } from "@/lib/api/contracts";
import { chainRoleView } from "./roles";

describe("chainRoleView — Rollenmatrix Zeile D", () => {
  it("Schichtleiter triggert und pinnt", () => {
    const view = chainRoleView("shift_lead");
    expect(view.canTrigger).toBe(true);
    expect(view.canPin).toBe(true);
    expect(view.aggregateOnly).toBe(false);
  });

  it("Techniker pinnt, triggert aber nicht", () => {
    const view = chainRoleView("technician");
    expect(view.canTrigger).toBe(false);
    expect(view.canPin).toBe(true);
  });

  it("Werker liest nur (kein Trigger, kein Pin)", () => {
    const view = chainRoleView("worker");
    expect(view).toEqual({ canTrigger: false, canPin: false, aggregateOnly: false });
  });

  it("Manager sieht nur das Aggregat", () => {
    expect(chainRoleView("manager").aggregateOnly).toBe(true);
  });

  it("unbekannte Rolle → default-deny", () => {
    expect(chainRoleView("unknown" as unknown as Role)).toEqual({
      canTrigger: false,
      canPin: false,
      aggregateOnly: false,
    });
  });
});
