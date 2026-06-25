// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/manifest.test.ts
//  Zweck: Prüft die Swap-Naht — die fünf Hauptklassen tragen echte GLBs, mixing_unit
//         (kein Asset) bleibt Platzhalter; der Dummy-GLB-Test belegt, dass der
//         Manifest-Eintrag injizierbar/austauschbar ist (reiner Daten-Swap).
//  Architektur-Einordnung: Test (Schicht 1), reine Logik.
// ============================================================
import { describe, expect, it } from "vitest";

import {
  CLASS_MODEL_MANIFEST,
  IDENTITY_TRANSFORM,
  type ModelSource,
  resolveModelSource,
} from "./manifest";

describe("resolveModelSource", () => {
  it("liefert für die fünf Hauptklassen ein GLB unter /synoptik/models", () => {
    expect(resolveModelSource("feeder")).toEqual({
      kind: "glb",
      url: "/synoptik/models/feeder.glb",
      transform: IDENTITY_TRANSFORM,
    });
    for (const machineClass of ["servo_press", "servo_axis", "robot"]) {
      expect(resolveModelSource(machineClass).kind).toBe("glb");
    }
    const vision = resolveModelSource("vision");
    expect(vision.kind).toBe("glb");
    if (vision.kind === "glb") {
      expect(vision.url).toBe("/synoptik/models/vision_station.glb");
    }
  });

  it("hält mixing_unit (kein Asset) als Platzhalter", () => {
    expect(resolveModelSource("mixing_unit")).toEqual({ kind: "placeholder" });
  });

  it("fällt für unbekannte oder fehlende Klassen sicher auf Platzhalter zurück", () => {
    expect(resolveModelSource("welder")).toEqual({ kind: "placeholder" });
    expect(resolveModelSource(null)).toEqual({ kind: "placeholder" });
  });

  it("greift beim Swap auf ein GLB durch (Dummy-GLB-Test) — kein Renderer-Umbau nötig", () => {
    // Simuliert das spätere Einhängen: nur der Manifest-Eintrag wird ersetzt.
    const swapped: Record<string, ModelSource> = {
      ...CLASS_MODEL_MANIFEST,
      feeder: {
        kind: "glb",
        url: "/test/feeder.dummy.glb",
        transform: { scale: 0.001, rotationY: Math.PI / 2, offset: { x: 0, y: 0.1, z: 0 } },
      },
    };

    const resolved = resolveModelSource("feeder", swapped);
    expect(resolved.kind).toBe("glb");
    if (resolved.kind === "glb") {
      expect(resolved.url).toBe("/test/feeder.dummy.glb");
      expect(resolved.transform.scale).toBeCloseTo(0.001, 6);
      expect(resolved.transform.rotationY).toBeCloseTo(Math.PI / 2, 6);
      expect(resolved.transform.offset).toEqual({ x: 0, y: 0.1, z: 0 });
    }
    // Nicht getauschte Klassen behalten ihren Manifest-Eintrag (mixing_unit = Platzhalter).
    expect(resolveModelSource("mixing_unit", swapped)).toEqual({ kind: "placeholder" });
  });

  it("hält eine neutrale Identitäts-Transform für vertragstreue GLBs bereit", () => {
    expect(IDENTITY_TRANSFORM).toEqual({ scale: 1, rotationY: 0, offset: { x: 0, y: 0, z: 0 } });
  });
});
