// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/placeholder-proportions.ts
//  Zweck: Pro Maschinenklasse ein proportional KORREKTER Blockout — grobe
//         Silhouette der echten Maschine (kein Würfel-Einerlei), in Metern. Der
//         Realismus kommt später aus den GLB-Modellen; bis dahin tragen diese
//         Proportionen die räumliche Lesbarkeit (flacher Förderer ≠ hohe Presse ≠
//         liegende Achse ≠ Roboter ≠ Kamera). Reine Daten — ohne THREE/DOM testbar.
//  Architektur-Einordnung: View-State (Schicht 2), ohne UI testbar.
// ============================================================

/** Grobe Silhouette der Klasse — steuert den Blockout-Aufbau im Renderer. */
export type PlaceholderShape = "conveyor" | "press" | "axis" | "robot" | "vision" | "generic";

export interface PlaceholderProportions {
  /** Ausdehnung ENTLANG der Linie (x, Materialfluss), in Metern. */
  width: number;
  /** Höhe (y), in Metern. */
  height: number;
  /** Tiefe QUER zur Linie (z), in Metern. */
  depth: number;
  /** Grobe Silhouette (für den Blockout-Aufbau, kein Einheits-Quader). */
  shape: PlaceholderShape;
}

// Proportionen je bekannter Klasse. Bewusst unterschiedliche Silhouetten, damit die
// Linie auch als Platzhalter räumlich lesbar ist (Maße ≈ realistische Größenordnung).
const PROPORTIONS: Record<string, PlaceholderProportions> = {
  feeder: { width: 2.6, height: 0.9, depth: 1.1, shape: "conveyor" }, // langer, flacher Förderer
  servo_press: { width: 1.4, height: 2.6, depth: 1.5, shape: "press" }, // hoher, kompakter Pressenrahmen
  servo_axis: { width: 1.8, height: 1.2, depth: 1.0, shape: "axis" }, // liegender Achs-/Portalbalken
  robot: { width: 1.1, height: 1.9, depth: 1.1, shape: "robot" }, // Sockel + Arm, mittelhoch
  vision: { width: 1.0, height: 1.7, depth: 1.0, shape: "vision" }, // Kamera am Portal/Ausleger
  mixing_unit: { width: 1.3, height: 1.6, depth: 1.3, shape: "generic" },
};

// Unbekannte/fehlende Klasse: neutraler, ehrlich generischer Blockout (kein erfundenes Modell).
const FALLBACK: PlaceholderProportions = { width: 1.2, height: 1.5, depth: 1.2, shape: "generic" };

/** Klasse → proportionaler Blockout; unbekannt/null → generischer Fallback. */
export function proportionsFor(machineClass: string | null): PlaceholderProportions {
  if (machineClass === null) {
    return FALLBACK;
  }
  return PROPORTIONS[machineClass] ?? FALLBACK;
}

/** Read-only-Tabelle der bekannten Proportionen (Doku/Test). */
export const PLACEHOLDER_PROPORTIONS: Readonly<Record<string, PlaceholderProportions>> = PROPORTIONS;
