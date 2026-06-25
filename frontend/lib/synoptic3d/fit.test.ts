// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/fit.test.ts
//  Zweck: Prüft die GLB-Normalisierung — uniform auf Klassen-Höhe skaliert,
//         Boden auf y = 0, x/z mittig (unabhängig von der nativen GLB-Einheit).
// ============================================================
import { describe, expect, it } from "vitest";

import { computeFit } from "./fit";

describe("computeFit", () => {
  it("skaliert uniform auf die Zielhöhe", () => {
    // 200 Einheiten hoch → Zielhöhe 2.6 m.
    const fit = computeFit({ min: { x: 0, y: 0, z: 0 }, max: { x: 50, y: 200, z: 30 } }, 2.6);
    expect(fit.scale).toBeCloseTo(2.6 / 200, 9);
  });

  it("verankert den Boden auf y = 0 (auch bei zentriertem/schwebendem Pivot)", () => {
    // Modell zentriert um den Ursprung (min.y negativ) → Boden muss auf 0 wandern.
    const fit = computeFit({ min: { x: -1, y: -123, z: -1 }, max: { x: 1, y: 93, z: 1 } }, 2.16);
    const scale = 2.16 / 216;
    expect(fit.scale).toBeCloseTo(scale, 9);
    // skalierter Boden (min.y) + offset.y == 0
    expect(-123 * scale + fit.offset.y).toBeCloseTo(0, 9);
  });

  it("zentriert x und z über dem Ursprung", () => {
    const fit = computeFit({ min: { x: -3.963, y: 1.095, z: -0.741 }, max: { x: 2.887, y: 13.27, z: 8.724 } }, 1.9);
    const scale = fit.scale;
    const centerX = (-3.963 + 2.887) / 2;
    const centerZ = (-0.741 + 8.724) / 2;
    expect(centerX * scale + fit.offset.x).toBeCloseTo(0, 9);
    expect(centerZ * scale + fit.offset.z).toBeCloseTo(0, 9);
  });

  it("fällt bei entarteter (null-hoher) Box auf Maßstab 1 zurück", () => {
    const fit = computeFit({ min: { x: 0, y: 5, z: 0 }, max: { x: 1, y: 5, z: 1 } }, 2);
    expect(fit.scale).toBe(1);
  });
});
