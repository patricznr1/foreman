// ============================================================
//  FOREMAN Frontend — lib/machine/geometry.test.ts
//  Zweck: Sichert die reine SVG-Geometrie (lineare Skalen + Pfad-Bau) des
//         TimeSeriesChart — ohne DOM testbar, deterministisch.
// ============================================================
import { describe, expect, it } from "vitest";

import { linePath, scaleLinear } from "./geometry";

describe("scaleLinear", () => {
  it("bildet Domänen-Enden auf Bereichs-Enden ab", () => {
    const s = scaleLinear([0, 10], [0, 100]);
    expect(s(0)).toBe(0);
    expect(s(10)).toBe(100);
    expect(s(5)).toBe(50);
  });

  it("unterstützt invertierten Bereich (Y-Achse: großer Wert → kleines y)", () => {
    const s = scaleLinear([0, 10], [200, 0]);
    expect(s(0)).toBe(200);
    expect(s(10)).toBe(0);
    expect(s(5)).toBe(100);
  });

  it("entartete Domäne (min == max) → Bereichsmitte statt NaN", () => {
    const s = scaleLinear([5, 5], [0, 100]);
    expect(s(5)).toBe(50);
    expect(Number.isNaN(s(99))).toBe(false);
  });
});

describe("linePath", () => {
  it("baut einen M/L-Pfad aus Punkten", () => {
    expect(
      linePath([
        { x: 0, y: 0 },
        { x: 10, y: 20 },
        { x: 20, y: 5 },
      ]),
    ).toBe("M0,0L10,20L20,5");
  });

  it("leere Punktliste → leerer Pfad", () => {
    expect(linePath([])).toBe("");
  });
});
