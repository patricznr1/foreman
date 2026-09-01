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

  it("lässt den Manager erfassen — er ist das Vorführprofil (seit 01.09.2026)", () => {
    // GEÄNDERT AM 01.09.2026. Vorher forderte dieser Fall das Gegenteil ein:
    // „lässt den Manager NUR lesen — erfasst nicht (Studie §4J)".
    //
    // WARUM ER SICH DREHT: GROUND_TRUTH §21 beschreibt das `manager`-Login als
    // Vorführprofil, mit dem sich „FOREMANs Fähigkeiten in EINEM Profil
    // vorführen" lassen — und die öffentliche Instanz führt genau dieses eine
    // Konto. Die Erfassung war davon ausgenommen, ohne dass es irgendwo stand.
    //
    // ES IST KEINE GRENZE, DIE HIER FÄLLT: `POST /worker_notes` kennt kein
    // `require_roles`. Der Server nahm die Notiz eines Managers seit jeher an;
    // nur diese Ansicht verbarg das Formular.
    const view = captureRoleView("manager");
    expect(view.canCapture).toBe(true);
    expect(view.showSuggestions).toBe(true);
    expect(view.readOnly).toBe(false);
    // Die Spracheingabe bleibt beim mobilen Werker (Studie §4J) — Darstellung,
    // keine Berechtigung.
    expect(view.voiceFirst).toBe(false);
  });

  it("hält den default-deny für unbekannte Rollen getrennt vom Manager", () => {
    // AUFBAU-KONTROLLE zur Änderung darüber: Dass der Manager jetzt erfassen
    // darf, darf den Rückfall für UNBEKANNTE Rollen nicht mitziehen. Beide
    // Fälle lasen vorher denselben Wert; nur einer sollte sich ändern.
    expect(captureRoleView("auditor" as never).canCapture).toBe(false);
    expect(captureRoleView("manager").canCapture).toBe(true);
  });

  it("fällt für unbekannte Backend-Rollen auf default-deny zurück (nur lesen)", () => {
    const view = captureRoleView("auditor" as never);
    expect(view.canCapture).toBe(false);
    expect(view.readOnly).toBe(true);
  });
});
