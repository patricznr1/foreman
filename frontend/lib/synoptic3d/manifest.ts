// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/manifest.ts
//  Zweck: Die SWAP-NAHT der 3D-Linie — Maschinenklasse → Modellquelle. HEUTE
//         liefert jede Klasse einen „placeholder"; das spätere Einhängen echter
//         GLB-Modelle ist ein reiner Daten-Swap (Eintrag auf { kind:"glb", url,
//         transform } setzen), KEIN Umbau am Renderer. Der Renderer fragt nur
//         resolveModelSource() und baut Platzhalter ODER lädt das GLB.
//
//  GLB-VERTRAG (Pflicht je Modell, damit der Swap ohne Renderer-Änderung greift):
//    • Maßstab in METERN (kein Zoll-Export → keine 40×-Maschine),
//    • Y-up (Three.js-Konvention),
//    • Pivot am BODEN-ZENTRUM (Maschine steht auf y = 0, mittig über x/z).
//  Reale Abweichungen einzelner Hersteller-Modelle werden NICHT am Asset, sondern
//  hier über ModelTransform (scale / rotationY / offset) je Klasse ausgeglichen.
//
//  OFFENE PUNKTE BEIM AKTIVIEREN (vom Platzhalter-PR bewusst in die Swap-Phase
//  verschoben, da der GLB-Pfad heute ruht — siehe synoptik-scene.tsx mountGlbModel):
//    • Das geladene GLB muss disposed werden (Geometrien/Materialien/Texturen) und
//      vor Unmount/Rebuild gegen eine Race abgesichert sein.
//    • Die GLB-Meshes müssen als Raycast-Ziele (machineId) registriert werden, sonst
//      bricht der Klick-Vertrag (machine_id → kanonische Karte).
//    • Status-Beacon/Boden-Ring sind aus den Platzhalter-Proportionen abgeleitet
//      (y = h + 0.3 bzw. Grundfläche aus w/d). Sie überleben den Swap bewusst, werden
//      aber NICHT automatisch an die echte GLB-Höhe/Grundfläche angepasst → den
//      ModelTransform.scale so wählen, dass die effektive GLB-Höhe nahe der Klassen-`h`
//      liegt (sonst sitzt das Beacon falsch).
//
//  Architektur-Einordnung: View-State (Schicht 2), ohne THREE/DOM testbar.
// ============================================================
import type { Vec3 } from "./types";

/** Feinjustage eines GLB gegen den GLB-Vertrag (Maßstab, Ausrichtung, Pivot-Offset). */
export interface ModelTransform {
  /** Uniformer Maßstabsfaktor (1 = Modell ist bereits in Metern). */
  scale: number;
  /** Drehung um die Y-Achse in Radiant (Ausrichtung in Flussrichtung). */
  rotationY: number;
  /** Boden-Zentrum-Pivot-Korrektur (Meter), falls das GLB nicht sauber zentriert ist. */
  offset: Vec3;
}

/** Modellquelle einer Klasse: heute Platzhalter, später ein optimiertes GLB. */
export type ModelSource =
  | { kind: "placeholder" }
  | { kind: "glb"; url: string; transform: ModelTransform };

/** Neutrale Transform (GLB erfüllt den Vertrag bereits). */
export const IDENTITY_TRANSFORM: ModelTransform = {
  scale: 1,
  rotationY: 0,
  offset: { x: 0, y: 0, z: 0 },
};

/** Geteilte Platzhalter-Quelle (alle Klassen heute). */
export const PLACEHOLDER_SOURCE: ModelSource = { kind: "placeholder" };

/**
 * Klasse → Modellquelle. HEUTE alle „placeholder". Späteres Einhängen:
 * z. B. `feeder: { kind: "glb", url: "/synoptik/models/feeder.glb", transform: … }`.
 */
export const CLASS_MODEL_MANIFEST: Record<string, ModelSource> = {
  feeder: PLACEHOLDER_SOURCE,
  servo_press: PLACEHOLDER_SOURCE,
  servo_axis: PLACEHOLDER_SOURCE,
  robot: PLACEHOLDER_SOURCE,
  vision: PLACEHOLDER_SOURCE,
  mixing_unit: PLACEHOLDER_SOURCE,
};

/**
 * Modellquelle einer Klasse auflösen. Unbekannte/fehlende Klasse → Platzhalter
 * (nie Fehler, nie Lücke). `manifest` ist injizierbar (Test/künftiger Swap).
 */
export function resolveModelSource(
  machineClass: string | null,
  manifest: Record<string, ModelSource> = CLASS_MODEL_MANIFEST,
): ModelSource {
  if (machineClass === null) {
    return PLACEHOLDER_SOURCE;
  }
  return manifest[machineClass] ?? PLACEHOLDER_SOURCE;
}
