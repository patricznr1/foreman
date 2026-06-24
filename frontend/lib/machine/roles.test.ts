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

  it("Manager: volles Sensor-Lagebild, aber nur Aggregat (keine Einzelaktion)", () => {
    const v = machineRoleView("manager");
    expect(v.sensorDetail).toBe("full"); // Desktop-Überblick, nicht die reduzierte Werker-Variante
    expect(v.aggregateOnly).toBe(true);
    expect(v.canCaptureNote).toBe(false);
  });
});
