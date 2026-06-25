// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/placeholder-proportions.test.ts
//  Zweck: Belegt, dass jede Klasse eine eigene, plausible Silhouette hat
//         (kein Würfel-Einerlei) und Unbekanntes/Fehlendes ehrlich generisch wird.
//  Architektur-Einordnung: Test (Schicht 1), reine Logik.
// ============================================================
import { describe, expect, it } from "vitest";

import { proportionsFor } from "./placeholder-proportions";

describe("proportionsFor", () => {
  it("gibt jeder bekannten Klasse ihre eigene Silhouette", () => {
    expect(proportionsFor("feeder").shape).toBe("conveyor");
    expect(proportionsFor("servo_press").shape).toBe("press");
    expect(proportionsFor("servo_axis").shape).toBe("axis");
    expect(proportionsFor("robot").shape).toBe("robot");
    expect(proportionsFor("vision").shape).toBe("vision");
  });

  it("ist kein Würfel-Einerlei — die fünf Hauptklassen haben verschiedene Silhouetten", () => {
    const shapes = new Set(
      ["feeder", "servo_press", "servo_axis", "robot", "vision"].map((c) => proportionsFor(c).shape),
    );
    expect(shapes.size).toBe(5);
    // Der flache Förderer ist niedriger und länger als die hohe, kompakte Presse.
    const feeder = proportionsFor("feeder");
    const press = proportionsFor("servo_press");
    expect(feeder.height).toBeLessThan(press.height);
    expect(feeder.width).toBeGreaterThan(press.width);
  });

  it("fällt für unbekannte oder fehlende Klassen auf einen generischen Blockout zurück", () => {
    expect(proportionsFor("welder").shape).toBe("generic");
    expect(proportionsFor(null).shape).toBe("generic");
  });

  it("liefert nur positive Maße (Meter)", () => {
    for (const c of ["feeder", "servo_press", "servo_axis", "robot", "vision", null]) {
      const p = proportionsFor(c);
      expect(p.width).toBeGreaterThan(0);
      expect(p.height).toBeGreaterThan(0);
      expect(p.depth).toBeGreaterThan(0);
    }
  });
});
