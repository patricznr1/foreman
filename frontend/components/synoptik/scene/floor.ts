// ============================================================
//  FOREMAN Frontend — components/synoptik/scene/floor.ts
//  Zweck: Dezenter Hallenboden (ruhige Grundfläche + feines Raster) auf y = 0.
//         Neutral und zurückhaltend (ISA-101-Ruhe) — er trägt die Linie, drängt
//         sich nicht auf. Szenen-Neutralfarben sind bewusst hartkodiert (Ästhetik),
//         die bedeutungstragenden Status-Farben kommen aus den Tokens.
//  Architektur-Einordnung: Renderer-Adapter (Schicht 3, nur Browser).
// ============================================================
import * as THREE from "three";

export interface FloorHandle {
  object: THREE.Group;
  dispose(): void;
}

/** Baut den Hallenboden (Platte + Raster), Pivot am Boden-Zentrum. */
export function buildFloor(lengthMeters: number): FloorHandle {
  const group = new THREE.Group();
  const span = Math.max(40, Math.ceil(lengthMeters * 1.4));

  const planeGeometry = new THREE.PlaneGeometry(span, span * 0.5);
  const planeMaterial = new THREE.MeshStandardMaterial({
    color: 0x161b22,
    roughness: 0.96,
    metalness: 0,
  });
  const plane = new THREE.Mesh(planeGeometry, planeMaterial);
  plane.rotation.x = -Math.PI / 2;
  plane.receiveShadow = false;
  group.add(plane);

  const grid = new THREE.GridHelper(span, span, 0x2a3340, 0x202832);
  const gridMaterial = grid.material;
  if (!Array.isArray(gridMaterial)) {
    gridMaterial.transparent = true;
    gridMaterial.opacity = 0.25;
  }
  group.add(grid);

  return {
    object: group,
    dispose() {
      planeGeometry.dispose();
      planeMaterial.dispose();
      grid.geometry.dispose();
      if (Array.isArray(grid.material)) {
        for (const material of grid.material) {
          material.dispose();
        }
      } else {
        grid.material.dispose();
      }
    },
  };
}
