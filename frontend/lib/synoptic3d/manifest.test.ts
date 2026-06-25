// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/manifest.test.ts
//  Zweck: Prüft die Swap-Naht — heute alle Klassen „placeholder", und der
//         Dummy-GLB-Test belegt, dass ein späteres Einhängen ein reiner Daten-Swap
//         ist (Eintrag auf { kind:"glb", … } setzen greift ohne Renderer-Änderung).
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
  it("liefert heute für jede bekannte Klasse einen Platzhalter", () => {
    for (const machineClass of Object.keys(CLASS_MODEL_MANIFEST)) {
      expect(resolveModelSource(machineClass)).toEqual({ kind: "placeholder" });
    }
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
        url: "/synoptik/models/feeder.glb",
        transform: { scale: 0.001, rotationY: Math.PI / 2, offset: { x: 0, y: 0.1, z: 0 } },
      },
    };

    const resolved = resolveModelSource("feeder", swapped);
    expect(resolved.kind).toBe("glb");
    if (resolved.kind === "glb") {
      expect(resolved.url).toBe("/synoptik/models/feeder.glb");
      expect(resolved.transform.scale).toBeCloseTo(0.001, 6);
      expect(resolved.transform.rotationY).toBeCloseTo(Math.PI / 2, 6);
      expect(resolved.transform.offset).toEqual({ x: 0, y: 0.1, z: 0 });
    }
    // Nicht getauschte Klassen bleiben Platzhalter.
    expect(resolveModelSource("servo_press", swapped)).toEqual({ kind: "placeholder" });
  });

  it("hält eine neutrale Identitäts-Transform für vertragstreue GLBs bereit", () => {
    expect(IDENTITY_TRANSFORM).toEqual({ scale: 1, rotationY: 0, offset: { x: 0, y: 0, z: 0 } });
  });
});
