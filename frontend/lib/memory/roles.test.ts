// ============================================================
//  FOREMAN Frontend — lib/memory/roles.test.ts
//  Zweck: Rollen-Varianten — Werker einfach, Manager aggregiert, Unbekannt default-deny.
// ============================================================
import { describe, expect, it } from "vitest";
import { memoryRoleView } from "./roles";
import type { Role } from "@/lib/api/contracts";

describe("memoryRoleView", () => {
  it("Werker: einfache Suche, große Karten, keine Filter/Verknüpfung", () => {
    const view = memoryRoleView("worker");
    expect(view.largeCards).toBe(true);
    expect(view.canFilter).toBe(false);
    expect(view.showRelations).toBe(false);
    expect(view.aggregateFirst).toBe(false);
  });

  it("Manager (Vollzugriff): Muster zuerst, aber voller Zugang inkl. Diagnose-Sprung", () => {
    // Werksleiter-/Vorführprofil (§21.12): behält die Muster-zuerst-Anordnung,
    // bekommt aber den Sprung in die Diagnose (Vollzugriff, keine Sackgasse).
    const view = memoryRoleView("manager");
    expect(view.aggregateFirst).toBe(true);
    expect(view.canFilter).toBe(true);
    expect(view.showRelations).toBe(true);
    expect(view.jumpToDiagnosis).toBe(true);
  });

  it("Techniker/Schichtleiter: volle Suche mit Sprung in Diagnose", () => {
    for (const role of ["technician", "shift_lead"] as Role[]) {
      const view = memoryRoleView(role);
      expect(view.canFilter).toBe(true);
      expect(view.jumpToDiagnosis).toBe(true);
    }
  });

  it("unbekannte Rolle erbt nie Rechte (default-deny)", () => {
    const view = memoryRoleView("ghost" as Role);
    expect(view).toEqual({
      canFilter: false,
      showRelations: false,
      aggregateFirst: false,
      largeCards: false,
      jumpToDiagnosis: false,
    });
  });
});
