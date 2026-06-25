// ============================================================
//  FOREMAN Frontend — components/synoptik/scene/placeholders.ts
//  Zweck: Baut pro Klasse einen proportional korrekten Blockout (grobe Silhouette,
//         kein Würfel-Einerlei): Förderer (lang/flach), Presse (hoher Portalrahmen),
//         Achse (liegender Balken), Roboter (Sockel+Arm), Vision (Portal+Kamera),
//         generisch (Fallback). Jede Maschine trägt ein recolorbares Status-Beacon
//         + Boden-Ring (Live-Status) und kann gehighlightet werden (Hover). Pivot am
//         Boden-Zentrum (y = 0) — exakt der GLB-Vertrag, damit der spätere Swap passt.
//  Architektur-Einordnung: Renderer-Adapter (Schicht 3, nur Browser).
// ============================================================
import * as THREE from "three";

import type { PlaceholderProportions, PlaceholderShape } from "@/lib/synoptic3d/placeholder-proportions";

export interface PlaceholderHandle {
  /** Boden-Zentrum-Gruppe; vom Aufrufer positioniert. */
  group: THREE.Group;
  /** Meshes, die für Klick/Hover raycastbar sind. */
  pickTargets: THREE.Mesh[];
  /** Status-Farbe (Beacon + Ring) setzen — Live-Umfärben ohne Neuaufbau. */
  setStatusColor(color: THREE.Color): void;
  /** Hover-Hervorhebung an/aus. */
  setHighlighted(on: boolean): void;
  dispose(): void;
}

const BODY_COLOR = 0x8b95a3; // neutrales Stahlgrau (Szenen-Neutralfarbe, kein Status)

export function buildPlaceholder(proportions: PlaceholderProportions): PlaceholderHandle {
  const { width: w, height: h, depth: d, shape } = proportions;
  const group = new THREE.Group();
  const geometries: THREE.BufferGeometry[] = [];
  const pickTargets: THREE.Mesh[] = [];

  const body = new THREE.MeshStandardMaterial({
    color: BODY_COLOR,
    metalness: 0.55,
    roughness: 0.5,
  });
  const status = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    emissive: 0xffffff,
    emissiveIntensity: 0.9,
    metalness: 0.1,
    roughness: 0.35,
    side: THREE.DoubleSide,
  });

  const addBox = (
    bw: number,
    bh: number,
    bd: number,
    x: number,
    y: number,
    z: number,
    rotZ = 0,
  ): void => {
    const geo = new THREE.BoxGeometry(bw, bh, bd);
    geometries.push(geo);
    const mesh = new THREE.Mesh(geo, body);
    mesh.position.set(x, y, z);
    mesh.rotation.z = rotZ;
    mesh.userData.isPlaceholderBody = true; // Swap-Naht: beim GLB-Tausch ausblendbar
    group.add(mesh);
    pickTargets.push(mesh);
  };

  const addCylinderAlongZ = (radius: number, length: number, x: number, y: number): void => {
    const geo = new THREE.CylinderGeometry(radius, radius, length, 20);
    geometries.push(geo);
    const mesh = new THREE.Mesh(geo, body);
    mesh.rotation.x = Math.PI / 2; // Achse von y nach z drehen (Rolle quer zur Linie)
    mesh.position.set(x, y, 0);
    mesh.userData.isPlaceholderBody = true;
    group.add(mesh);
    pickTargets.push(mesh);
  };

  const addBase = (radius: number, height: number): void => {
    const geo = new THREE.CylinderGeometry(radius, radius, height, 24);
    geometries.push(geo);
    const mesh = new THREE.Mesh(geo, body);
    mesh.position.set(0, height / 2, 0);
    mesh.userData.isPlaceholderBody = true;
    group.add(mesh);
    pickTargets.push(mesh);
  };

  buildShape(shape, { w, h, d }, { addBox, addCylinderAlongZ, addBase });

  // Status-Beacon (Leuchtkugel) auf der Maschine + Boden-Ring — beide recolorbar.
  const beaconGeometry = new THREE.SphereGeometry(0.17, 18, 12);
  geometries.push(beaconGeometry);
  const beacon = new THREE.Mesh(beaconGeometry, status);
  beacon.position.set(0, h + 0.3, 0);
  group.add(beacon);
  pickTargets.push(beacon);

  const ringOuter = Math.max(w, d) * 0.62;
  const ringGeometry = new THREE.RingGeometry(ringOuter * 0.8, ringOuter, 36);
  geometries.push(ringGeometry);
  const ring = new THREE.Mesh(ringGeometry, status);
  ring.rotation.x = -Math.PI / 2;
  ring.position.set(0, 0.02, 0);
  group.add(ring);
  pickTargets.push(ring); // sichtbare Statusfläche bleibt klick-/hoverbar

  return {
    group,
    pickTargets,
    setStatusColor(color: THREE.Color): void {
      status.color.copy(color);
      status.emissive.copy(color);
    },
    setHighlighted(on: boolean): void {
      body.emissive.setHex(on ? 0x2a3a4d : 0x000000);
      body.emissiveIntensity = on ? 0.7 : 0;
      status.emissiveIntensity = on ? 1.7 : 0.9;
    },
    dispose(): void {
      for (const geometry of geometries) {
        geometry.dispose();
      }
      body.dispose();
      status.dispose();
    },
  };
}

interface ShapeBuilders {
  addBox: (bw: number, bh: number, bd: number, x: number, y: number, z: number, rotZ?: number) => void;
  addCylinderAlongZ: (radius: number, length: number, x: number, y: number) => void;
  addBase: (radius: number, height: number) => void;
}

interface Dims {
  w: number;
  h: number;
  d: number;
}

/** Setzt die klassen-typische Silhouette aus Primitiven zusammen (Pivot Boden-Zentrum). */
function buildShape(shape: PlaceholderShape, dims: Dims, b: ShapeBuilders): void {
  const { w, h, d } = dims;
  switch (shape) {
    case "conveyor": {
      // Langer, flacher Förderer: Rahmen + Band + zwei Endrollen.
      b.addBox(w * 0.94, h * 0.45, d * 0.6, 0, h * 0.3, 0);
      b.addBox(w, h * 0.12, d * 0.5, 0, h * 0.62, 0);
      b.addCylinderAlongZ(h * 0.2, d * 0.55, -w * 0.45, h * 0.55);
      b.addCylinderAlongZ(h * 0.2, d * 0.55, w * 0.45, h * 0.55);
      return;
    }
    case "press": {
      // Hoher, kompakter Pressenrahmen: Basis, zwei Ständer, Querhaupt, Stößel.
      b.addBox(w, h * 0.12, d, 0, h * 0.06, 0);
      b.addBox(w * 0.18, h * 0.78, d * 0.5, -w * 0.36, h * 0.52, 0);
      b.addBox(w * 0.18, h * 0.78, d * 0.5, w * 0.36, h * 0.52, 0);
      b.addBox(w, h * 0.16, d * 0.6, 0, h * 0.92, 0);
      b.addBox(w * 0.36, h * 0.3, d * 0.42, 0, h * 0.62, 0);
      return;
    }
    case "axis": {
      // Liegender Achs-/Portalbalken auf zwei kurzen Füßen + Schlitten.
      b.addBox(w * 0.12, h * 0.6, d * 0.4, -w * 0.42, h * 0.3, 0);
      b.addBox(w * 0.12, h * 0.6, d * 0.4, w * 0.42, h * 0.3, 0);
      b.addBox(w, h * 0.24, d * 0.4, 0, h * 0.74, 0);
      b.addBox(w * 0.22, h * 0.22, d * 0.55, 0, h * 0.74, 0);
      return;
    }
    case "robot": {
      // Sockel + drehbare Säule + geknickter Arm (Roboter-Silhouette).
      b.addBase(w * 0.42, h * 0.16);
      b.addBox(w * 0.52, h * 0.42, d * 0.52, 0, h * 0.34, 0);
      b.addBox(w * 0.9, h * 0.16, d * 0.22, w * 0.08, h * 0.64, 0, -Math.PI / 5);
      b.addBox(h * 0.16, h * 0.5, d * 0.2, w * 0.42, h * 0.82, 0, Math.PI / 8);
      return;
    }
    case "vision": {
      // Portal mit hängender Kamera + Objektiv (Endkontrolle).
      b.addBox(w * 0.12, h * 0.85, d * 0.12, -w * 0.4, h * 0.42, 0);
      b.addBox(w * 0.12, h * 0.85, d * 0.12, w * 0.4, h * 0.42, 0);
      b.addBox(w, h * 0.12, d * 0.16, 0, h * 0.85, 0);
      b.addBox(w * 0.32, h * 0.22, d * 0.32, 0, h * 0.62, 0);
      b.addBox(w * 0.16, h * 0.12, d * 0.16, 0, h * 0.48, 0); // Objektiv unter der Kamera
      return;
    }
    default: {
      // Generisch: abgesetzter Block (ehrlicher Fallback, kein erfundenes Modell).
      b.addBox(w * 0.82, h * 0.85, d * 0.82, 0, h * 0.45, 0);
      b.addBox(w * 0.5, h * 0.16, d * 0.5, 0, h * 0.93, 0);
      return;
    }
  }
}
