// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/fit.ts
//  Zweck: Normalisiert ein beliebig skaliertes/positioniertes GLB auf den
//         GLB-Vertrag — uniform auf die Klassen-Zielhöhe skaliert und am
//         Boden-Zentrum verankert (Boden auf y = 0, x/z mittig). Die echten
//         Hersteller-GLBs kommen in völlig verschiedenen Einheiten (cm/mm/„units"),
//         daher ist dies der eigentliche Render-Kohärenz-Schritt: gleiche Maßstabs-
//         Logik für alle, statt fünf hand-getunte Transforms. Reine Funktion —
//         ohne THREE/DOM testbar; der Renderer wendet das Ergebnis auf das Modell an.
//  Architektur-Einordnung: View-State (Schicht 2), ohne UI testbar.
// ============================================================
import type { Vec3 } from "./types";

/** Achsen-ausgerichtete Bounding-Box eines Modells (Modellraum, vor Transform). */
export interface Box {
  min: Vec3;
  max: Vec3;
}

/** Uniformer Maßstab + Boden-Zentrum-Offset, der die Box auf targetHeight bringt. */
export interface FitTransform {
  scale: number;
  offset: Vec3;
}

/**
 * Berechnet Maßstab und Offset, um `box` uniform auf `targetHeight` (Meter) zu
 * skalieren und so zu verschieben, dass die skalierte Box mit dem Boden auf y = 0
 * steht und in x/z mittig über dem Ursprung sitzt (Boden-Zentrum-Pivot).
 */
export function computeFit(box: Box, targetHeight: number): FitTransform {
  const height = box.max.y - box.min.y;
  const scale = height > 0 ? targetHeight / height : 1;
  const centerX = (box.min.x + box.max.x) / 2;
  const centerZ = (box.min.z + box.max.z) / 2;
  return {
    scale,
    offset: {
      x: -centerX * scale,
      y: -box.min.y * scale,
      z: -centerZ * scale,
    },
  };
}
