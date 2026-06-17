// ============================================================
//  FOREMAN Frontend — lib/capture/roles.test.ts
//  Zweck: Sichert die Rollen-Varianten der Erfassung (Matrix 3.1 + §4J).
// ============================================================
import { describe, expect, it } from "vitest";
import { captureRoleView } from "./roles";

describe("captureRoleView", () => {
  it("macht den Werker zum Kernnutzer (erfasst, Sprache zuerst angeboten)", () => {
    const view = captureRoleView("worker");
    expect(view.canCapture).toBe(true);
    expect(view.voiceFirst).toBe(true);
    expect(view.readOnly).toBe(false);
  });

  it("lässt Schichtleiter und Techniker erfassen (mit Kontextvorschlägen)", () => {
    for (const role of ["shift_lead", "technician"] as const) {
      const view = captureRoleView(role);
      expect(view.canCapture).toBe(true);
      expect(view.showSuggestions).toBe(true);
      expect(view.readOnly).toBe(false);
    }
  });

  it("lässt den Manager NUR lesen — erfasst nicht (Studie §4J)", () => {
    const view = captureRoleView("manager");
    expect(view.canCapture).toBe(false);
    expect(view.readOnly).toBe(true);
  });

  it("fällt für unbekannte Backend-Rollen auf default-deny zurück (nur lesen)", () => {
    const view = captureRoleView("auditor" as never);
    expect(view.canCapture).toBe(false);
    expect(view.readOnly).toBe(true);
  });
});
