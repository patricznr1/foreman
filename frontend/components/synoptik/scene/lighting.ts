// ============================================================
//  FOREMAN Frontend — components/synoptik/scene/lighting.ts
//  Zweck: EINE geteilte, neutrale Szenenbeleuchtung (Key/Fill/Ambient) + ein
//         Environment/IBL aus einer neutralen Innenraum-Umgebung — bewusst ZENTRAL,
//         nicht pro Modell. Das ist der Render-Kohärenz-Hebel: damit später ein
//         Hersteller-Mix verschiedener GLBs unter EINEM Licht kohärent wirkt.
//         ACESFilmic-Tonemapping wird am Renderer gesetzt (filmische, ruhige Rampe).
//  Architektur-Einordnung: Renderer-Adapter (Schicht 3, nur Browser).
// ============================================================
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

export interface LightingHandle {
  dispose(): void;
}

/** Setzt geteilte Beleuchtung + IBL + ACESFilmic auf Szene/Renderer. */
export function setupLighting(scene: THREE.Scene, renderer: THREE.WebGLRenderer): LightingHandle {
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1;

  const ambient = new THREE.AmbientLight(0xffffff, 0.3);
  const key = new THREE.DirectionalLight(0xffffff, 2.4);
  key.position.set(6, 11, 7);
  const fill = new THREE.DirectionalLight(0xffffff, 0.9);
  fill.position.set(-9, 6, -5);
  scene.add(ambient, key, fill);

  // Neutrale Innenraum-Umgebung als IBL → kohärente Reflexe/Spiegelungen über alle
  // (späteren) Modelle hinweg. Aus einer PMREM-Map der RoomEnvironment.
  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  const envTexture = pmrem.fromScene(room, 0.04).texture;
  scene.environment = envTexture;

  return {
    dispose() {
      scene.remove(ambient, key, fill);
      scene.environment = null;
      envTexture.dispose();
      pmrem.dispose();
      room.dispose(); // RoomEnvironment-Geometrien/Materialien freigeben
    },
  };
}
