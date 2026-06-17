// ============================================================
//  FOREMAN Frontend — lib/prediction/roles.test.ts
//  Zweck: Rollen-Varianten (§3.1/§4E) — Werker ohne Trigger, Manager nur Aggregat.
// ============================================================
import { describe, expect, it } from "vitest";
import type { Role } from "@/lib/api/contracts";
import { predictionRoleView } from "./roles";

describe("predictionRoleView", () => {
  it("Werker: liest knapp, ohne Trigger, ohne Entscheidung, ohne Faktor-Detail", () => {
    expect(predictionRoleView("worker")).toEqual({
      canTrigger: false,
      canDecide: false,
      factorDetail: false,
      aggregateOnly: false,
    });
  });

  it("Schichtleiter: fordert an und quittiert (Trigger + Entscheidung + Faktor-Detail)", () => {
    const v = predictionRoleView("shift_lead");
    expect(v.canTrigger).toBe(true);
    expect(v.canDecide).toBe(true);
    expect(v.factorDetail).toBe(true);
    expect(v.aggregateOnly).toBe(false);
  });

  it("Techniker: liest mit Faktor-Detail, aber ohne Trigger/Entscheidung", () => {
    const v = predictionRoleView("technician");
    expect(v.factorDetail).toBe(true);
    expect(v.canTrigger).toBe(false);
    expect(v.canDecide).toBe(false);
  });

  it("Manager: nur Aggregat, nie die Einzelempfehlung, kein Trigger", () => {
    const v = predictionRoleView("manager");
    expect(v.aggregateOnly).toBe(true);
    expect(v.canTrigger).toBe(false);
    expect(v.canDecide).toBe(false);
  });

  it("unbekannte Backend-Rolle → restriktivster Default (default-deny)", () => {
    const v = predictionRoleView("ghost" as Role);
    expect(v).toEqual({
      canTrigger: false,
      canDecide: false,
      factorDetail: false,
      aggregateOnly: false,
    });
  });
});
