// ============================================================
//  FOREMAN Frontend — lib/auth/roles.test.ts
//  Zweck: Rollenmatrix 3.1 ist durchgesetzt — Ausschlüsse (○) greifen, Navigation
//         bleibt ≤ 7 und ohne aktionslose Einträge, Landing je Rolle korrekt.
//  Architektur-Einordnung: Quality-Gate (Akzeptanzkriterium Rollen-Routing).
// ============================================================
import { describe, expect, it } from "vitest";
import type { Role } from "../api/contracts";
import { ACCESS_MATRIX, canAccessSection, landingRoute, visibleNav } from "./roles";

const ROLES: readonly Role[] = ["worker", "shift_lead", "technician", "manager"];

describe("Rollenmatrix 3.1", () => {
  it("Werker und Techniker haben keinen Zugriff auf Cockpit (A) und Plattform (I)", () => {
    for (const role of ["worker", "technician"] as const) {
      expect(canAccessSection(role, "A")).toBe(false);
      expect(canAccessSection(role, "I")).toBe(false);
    }
  });

  it("Cockpit nur Manager (voll) und Schichtleiter (reduziert)", () => {
    expect(ACCESS_MATRIX.A.manager).toBe("full");
    expect(ACCESS_MATRIX.A.shift_lead).toBe("reduced");
    expect(ACCESS_MATRIX.A.worker).toBe("none");
    expect(ACCESS_MATRIX.A.technician).toBe("none");
  });

  it("jede Rolle: ≤ 7 BEGEHBARE Navigationseinträge, keiner ohne zugehörigen Zugriff", () => {
    for (const role of ROLES) {
      const nav = visibleNav(role);
      expect(nav.length).toBeGreaterThan(0);
      // ≤ 7 begehbare Einträge (Designstudie §3.3); ein deaktivierter Vorschau-Eintrag
      // ("Hatten wir das schon mal", Paket 1c) zählt NICHT zu den begehbaren.
      const actionable = nav.filter((item) => !item.disabled && item.href !== null);
      expect(actionable.length).toBeLessThanOrEqual(7);
      for (const item of nav) {
        expect(item.sections.some((section) => canAccessSection(role, section))).toBe(true);
      }
    }
  });

  it("Sektion H heißt im Nav 'Archiv' (Route /archive)", () => {
    const archive = visibleNav("worker").find((item) => item.id === "archive");
    expect(archive?.label).toBe("Archiv");
    expect(archive?.href).toBe("/archive");
  });

  it("'Hatten wir das schon mal' ist sichtbar, aber deaktiviert (kein Routing-Ziel)", () => {
    const recall = visibleNav("worker").find((item) => item.id === "recall");
    expect(recall).toBeDefined();
    expect(recall?.disabled).toBe(true);
    expect(recall?.href).toBeNull();
    expect(recall?.label).toBe("Hatten wir das schon mal");
  });

  it("Werker sieht weder Cockpit noch Plattform, aber Maschinen und Erfassung", () => {
    const ids = visibleNav("worker").map((item) => item.id);
    expect(ids).not.toContain("cockpit");
    expect(ids).not.toContain("platform");
    expect(ids).toContain("machines");
    expect(ids).toContain("capture");
  });

  it("Manager sieht Cockpit und Plattform", () => {
    const ids = visibleNav("manager").map((item) => item.id);
    expect(ids).toContain("cockpit");
    expect(ids).toContain("platform");
  });

  it("landingRoute(): Manager/Schichtleiter → Cockpit, Werker/Techniker → Maschinen", () => {
    expect(landingRoute("manager")).toBe("/overview");
    expect(landingRoute("shift_lead")).toBe("/overview");
    expect(landingRoute("worker")).toBe("/machines");
    expect(landingRoute("technician")).toBe("/machines");
  });

  it("landingRoute(): unbekannte Rolle → sicherer /login-Fallback (keine Redirect-Schleife)", () => {
    expect(landingRoute("ghost" as Role)).toBe("/login");
  });
});
