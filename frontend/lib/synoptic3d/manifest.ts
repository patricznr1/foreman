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
//  NORMALISIERUNG (Renderer): die nativen Hersteller-GLBs kommen in völlig
//  verschiedenen Einheiten/Pivots (cm/mm/„units", zentriert vs. schwebend). placeGlb
//  (scene/glb.ts) skaliert daher jedes Modell UNIFORM auf die Klassen-Zielhöhe
//  (placeholder-proportions) und verankert es am Boden-Zentrum — der eigentliche
//  Render-Kohärenz-Schritt. Weil die effektive Höhe == Klassen-`h` ist, sitzt das
//  Status-Beacon (h + 0.3) automatisch richtig. GLB-Disposal, Unmount-Race-Schutz und
//  die Raycast-Registrierung der GLB-Meshes (Klick-Vertrag) übernimmt der Renderer
//  (synoptik-scene.tsx loadGlbForMachine). ModelTransform.rotationY/offset/scale
//  bleiben für visuelle Feinjustage je Modell (Ausrichtung in Flussrichtung etc.) —
//  Default Identität.
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

/** GLB-Quelle unter /public/synoptik/models/ (Draco, plain-Variante — die KTX2-
 *  Varianten werden bewusst nicht genutzt, daher kein Basis-Transcoder nötig). */
function glbModel(file: string): ModelSource {
  return { kind: "glb", url: `/synoptik/models/${file}`, transform: IDENTITY_TRANSFORM };
}

/**
 * Klasse → Modellquelle. Die fünf Hauptklassen tragen echte GLBs; `mixing_unit` hat
 * kein Asset und bleibt Platzhalter (kommt im 12-Maschinen-Park ohnehin nicht vor).
 */
export const CLASS_MODEL_MANIFEST: Record<string, ModelSource> = {
  feeder: glbModel("feeder.glb"),
  servo_press: glbModel("servo_press.glb"),
  servo_axis: glbModel("servo_axis.glb"),
  robot: glbModel("robot.glb"),
  vision: glbModel("vision_station.glb"),
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
