// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/status-color.test.ts
//  Zweck: Belegt, dass die 3D-Status-Farbe dieselbe Quelle nutzt wie Cockpit/Karte
//         (MACHINE_STATUS_TO_FCSM + FCSM_TOKEN) — keine eigene Palette.
//  Architektur-Einordnung: Test (Schicht 1), reine Logik.
// ============================================================
import { describe, expect, it } from "vitest";

import { statusColorVar, statusFcsm } from "./status-color";

describe("statusFcsm", () => {
  it("bildet den komponierten Status auf den FCSM-Zustand ab", () => {
    expect(statusFcsm("healthy")).toBe("ok");
    expect(statusFcsm("drift_active")).toBe("outofspec");
    expect(statusFcsm("open_warning")).toBe("check");
  });
});

describe("statusColorVar", () => {
  it("liefert die CSS-Custom-Property der Status-Farbe (Design-Token)", () => {
    expect(statusColorVar("healthy")).toBe("--color-state-ok");
    expect(statusColorVar("drift_active")).toBe("--color-state-outofspec");
    expect(statusColorVar("open_warning")).toBe("--color-state-check");
  });
});
