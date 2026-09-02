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

  it("jede Rolle: ≤ 8 BEGEHBARE Navigationseinträge, keiner ohne zugehörigen Zugriff", () => {
    for (const role of ROLES) {
      const nav = visibleNav(role);
      expect(nav.length).toBeGreaterThan(0);
      // ≤ 8 begehbare Einträge. Die Studie §3.3 nannte 7 und rechnete den
      // Vorschau-Eintrag "Hatten wir das schon mal" nicht mit, weil er deaktiviert
      // war. Seit dem 02.09.2026 führt er in die Verknüpfungs-Ansicht und ist
      // begehbar — die Zahl der SICHTBAREN Einträge hat sich damit nicht geändert,
      // nur ihr Zustand. Die Grenze wandert deshalb um genau diesen einen mit
      // (GROUND_TRUTH §21.16), nicht ins Offene: Sie bleibt eine Grenze.
      const actionable = nav.filter((item) => !item.disabled && item.href !== null);
      expect(actionable.length).toBeLessThanOrEqual(8);
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

  it("'Hatten wir das schon mal' führt in die Verknüpfungs-Ansicht", () => {
    // Der Eintrag stand seit Paket 1c dauerhaft ausgegraut da ("folgt mit echter
    // Substanz"). Die Substanz ist seit dem 27.08.2026 angebunden — die vierte
    // Quelle — und seit dem 28.08.2026 trägt jede Erinnerung ihr Bauteil.
    // Ein grauer Eintrag, der ankündigt, was nebenan längst läuft, ist
    // irreführender als gar keiner.
    const recall = visibleNav("worker").find((item) => item.id === "recall");
    expect(recall).toBeDefined();
    expect(recall?.disabled).toBeUndefined();
    expect(recall?.label).toBe("Hatten wir das schon mal");
    // Der Parameter ist tragend: OHNE ihn landet der Eintrag auf der wörtlichen
    // Suche über alle vier Quellen und hielte sein Versprechen nicht.
    expect(recall?.href).toBe("/archive?quelle=gedaechtnis");
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
