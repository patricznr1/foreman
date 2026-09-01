// ============================================================
//  FOREMAN Frontend — lib/machine/roles.test.ts
//  Zweck: Sichert die Rollen-Varianten der Maschinen-Detail-Sicht (Matrix 3.1 / §4B).
// ============================================================
import { describe, expect, it } from "vitest";

import { machineRoleView } from "./roles";

describe("machineRoleView", () => {
  it("Werker: Notiz ja, kein Vorhersage-Trigger, reduzierte Sensorauswahl", () => {
    const v = machineRoleView("worker");
    expect(v.canCaptureNote).toBe(true);
    expect(v.canRequestPrediction).toBe(false);
    expect(v.canAcknowledge).toBe(false);
    expect(v.sensorDetail).toBe("reduced");
    expect(v.aggregateOnly).toBe(false);
  });

  it("Schichtleiter: voll — Vorhersage anfordern + quittieren", () => {
    const v = machineRoleView("shift_lead");
    expect(v.canRequestPrediction).toBe(true);
    expect(v.canAcknowledge).toBe(true);
    expect(v.sensorDetail).toBe("full");
  });

  it("Techniker: Diagnose-Tiefe + Offline-Cache, kein Trigger", () => {
    const v = machineRoleView("technician");
    expect(v.sensorDetail).toBe("full");
    expect(v.factorContext).toBe(true);
    expect(v.offlineCache).toBe(true);
    expect(v.canRequestPrediction).toBe(false);
  });

  it("Manager: volles Lagebild UND alle drei Einzelaktionen (seit 01.09.2026)", () => {
    // GEÄNDERT AM 01.09.2026. Vorher hiess dieser Fall „…aber nur Aggregat
    // (keine Einzelaktion)" und forderte `canCaptureNote === false`.
    //
    // WAS IHN GEDREHT HAT: Jede der drei Aktionen erlaubt der SERVER dem Manager
    // seit jeher — Notiz erfassen (kein `require_roles`), Vorhersage anfordern
    // (`SHIFT_LEAD, MANAGER`), quittieren (`SHIFT_LEAD, TECHNICIAN, MANAGER`).
    // Diese Ansicht verbarg drei Knöpfe, die die Autorisierung bedient hätte.
    // Der Kopfkommentar der Quelldatei sagte „keine Einzelaktion" und schrieb in
    // derselben Matrix-Zeile `manager full` — beides konnte nicht stimmen.
    const v = machineRoleView("manager");
    expect(v.canCaptureNote).toBe(true);
    expect(v.canRequestPrediction).toBe(true);
    expect(v.canAcknowledge).toBe(true);
    expect(v.factorContext).toBe(true); // wer die Zahl auslöst, braucht ihre Faktoren
    // Unverändert: Beides ist DARSTELLUNG, nicht Berechtigung.
    expect(v.sensorDetail).toBe("full"); // Desktop-Überblick, nicht die reduzierte Werker-Variante
    expect(v.aggregateOnly).toBe(true); // Flottenblick statt Einzelwert
  });

  it("die Sichtbarkeit bleibt ≤ Server-Autorisierung", () => {
    // DIE REGEL AUS DEM KOPFKOMMENTAR, eingefordert statt behauptet.
    //
    // Sie ist die eigentliche Zusicherung dieser Datei: Eine Ansicht darf einen
    // Knopf VERBERGEN, den der Server erlaubt — nie einen zeigen, den er
    // ablehnt. Sonst führt ein Klick zu 403, und der Nutzer sieht ein Angebot,
    // das keines ist.
    //
    // Abgebildet ist der Stand des Servers vom 01.09.2026, von Hand
    // nachgezählt. Wer eine Route enger stellt, muss hier vorbeikommen.
    const serverErlaubt: Record<string, readonly string[]> = {
      canCaptureNote: ["worker", "shift_lead", "technician", "manager"], // kein require_roles
      canRequestPrediction: ["shift_lead", "manager"],
      canAcknowledge: ["shift_lead", "technician", "manager"],
    };
    for (const rolle of ["worker", "shift_lead", "technician", "manager"] as const) {
      const v = machineRoleView(rolle);
      for (const [flag, erlaubte] of Object.entries(serverErlaubt)) {
        if (v[flag as keyof typeof v] === true) {
          expect(erlaubte, `${rolle}.${flag} ist sichtbar, aber der Server lehnt ab`).toContain(
            rolle,
          );
        }
      }
    }
  });
});
