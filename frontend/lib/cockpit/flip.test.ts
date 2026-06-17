// ============================================================
//  FOREMAN Frontend — lib/cockpit/flip.test.ts
//  Zweck: Sichert die Kipp-Erkennung (§4A/§5.6): NEU in Abweichung gekippte Zellen
//         pulsen einmal — beim ersten Aufbau pulst nichts (kein Öffnen-Blitz).
// ============================================================
import { describe, expect, it } from "vitest";

import { detectKipps, snapshotKinds } from "./flip";
import type { CellKind, HeatmapCell } from "./types";

function cell(machineId: number, kind: CellKind): HeatmapCell {
  return {
    machineId,
    label: `M${machineId}`,
    machineClass: "Presse",
    lineId: 1,
    status: kind === "drift" ? "drift_active" : kind === "warning" ? "open_warning" : "healthy",
    fcsm: "ok",
    level: kind === "healthy" ? 0 : 2,
    kind,
    openAlarmCount: kind === "healthy" ? 0 : 1,
    criticalCount: 0,
  };
}

describe("detectKipps", () => {
  it("erster Aufbau (leere Vorgeschichte) → kein Kipp (kein Öffnen-Blitz)", () => {
    const kipped = detectKipps(new Map(), [cell(1, "drift"), cell(2, "warning")]);
    expect(kipped.size).toBe(0);
  });

  it("ruhig → Drift bzw. ruhig → Warnung kippt", () => {
    const prev = snapshotKinds([cell(1, "healthy"), cell(2, "healthy")]);
    const kipped = detectKipps(prev, [cell(1, "drift"), cell(2, "warning")]);
    expect([...kipped].sort()).toEqual([1, 2]);
  });

  it("bereits auffällig → kein erneuter Puls", () => {
    const prev = snapshotKinds([cell(1, "warning"), cell(2, "drift")]);
    const kipped = detectKipps(prev, [cell(1, "drift"), cell(2, "drift")]);
    expect(kipped.size).toBe(0);
  });

  it("neue, vorher unbekannte Maschine → kein Puls", () => {
    const prev = snapshotKinds([cell(1, "healthy")]);
    const kipped = detectKipps(prev, [cell(1, "healthy"), cell(99, "drift")]);
    expect(kipped.size).toBe(0);
  });
});
