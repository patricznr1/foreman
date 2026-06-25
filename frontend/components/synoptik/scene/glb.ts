// ============================================================
//  FOREMAN Frontend — components/synoptik/scene/glb.ts
//  Zweck: Normalisiert ein geladenes GLB auf den GLB-Vertrag und platziert es am
//         Boden-Zentrum: uniform auf die Klassen-Zielhöhe (× optionalem
//         transform.scale) skaliert, Boden auf y = 0, x/z mittig, optional um Y
//         gedreht + fein verschoben. So wirken die in völlig verschiedenen Einheiten
//         gelieferten Hersteller-GLBs unter EINEM Maßstab kohärent. Mutiert das
//         Modell — THREE-seitig, aber ohne WebGL (jsdom) testbar.
//  Architektur-Einordnung: Renderer-Adapter (Schicht 3).
// ============================================================
import * as THREE from "three";

import { computeFit } from "@/lib/synoptic3d/fit";
import type { ModelTransform } from "@/lib/synoptic3d/manifest";

/** Skaliert/verankert ein geladenes GLB auf die Klassen-Höhe am Boden-Zentrum. */
export function placeGlb(
  model: THREE.Object3D,
  targetHeight: number,
  transform: ModelTransform,
): void {
  const box = new THREE.Box3().setFromObject(model);
  const effectiveHeight = targetHeight * transform.scale;
  const fit = computeFit({ min: box.min, max: box.max }, effectiveHeight);

  model.scale.setScalar(fit.scale);
  model.position.set(
    fit.offset.x + transform.offset.x,
    fit.offset.y + transform.offset.y,
    fit.offset.z + transform.offset.z,
  );
  model.rotation.y = transform.rotationY;
}
