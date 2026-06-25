// ============================================================
//  FOREMAN Frontend — components/synoptik/scene/loaders.ts
//  Zweck: Die GLB-Lade-Pipeline GLEICH eingerichtet (GLTFLoader nativ +
//         DRACOLoader + KTX2Loader + MeshoptDecoder) — heute RUHEND, weil alle
//         Maschinen Platzhalter sind. Beim Swap (Manifest-Eintrag → { kind:"glb" })
//         lädt der Renderer hierüber, ohne Umbau. Dekoder-Assets liegen unter
//         /public/synoptik/decoders/* und müssen erst zum Swap-Zeitpunkt vorhanden
//         sein (Draco-Decoder + Basis-Transcoder).
//  Architektur-Einordnung: Renderer-Adapter (Schicht 3, nur Browser).
// ============================================================
import * as THREE from "three";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { KTX2Loader } from "three/examples/jsm/loaders/KTX2Loader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";

/** Basis-Pfad der Dekoder-Assets (Draco/Basis). Zum GLB-Swap zu befüllen. */
export const DECODER_BASE = "/synoptik/decoders/";

export interface ModelLoader {
  /** Lädt ein optimiertes GLB (Draco/meshopt/KTX2) und gibt seine Szene zurück. */
  loadGlb(url: string): Promise<THREE.Group>;
  dispose(): void;
}

/**
 * Richtet die volle GLB-Pipeline ein. Wird heute nicht ausgelöst (kein GLB im
 * Manifest); die Wiring beweist die Swap-Bereitschaft (Draco/meshopt/KTX2).
 */
export function createModelLoader(renderer: THREE.WebGLRenderer): ModelLoader {
  const draco = new DRACOLoader().setDecoderPath(`${DECODER_BASE}draco/`);
  const ktx2 = new KTX2Loader().setTranscoderPath(`${DECODER_BASE}basis/`).detectSupport(renderer);

  const gltf = new GLTFLoader();
  gltf.setDRACOLoader(draco);
  gltf.setKTX2Loader(ktx2);
  gltf.setMeshoptDecoder(MeshoptDecoder);

  return {
    loadGlb(url: string): Promise<THREE.Group> {
      return new Promise((resolve, reject) => {
        gltf.load(
          url,
          (model) => resolve(model.scene),
          undefined,
          (error) => reject(error instanceof Error ? error : new Error(String(error))),
        );
      });
    },
    dispose() {
      draco.dispose();
      ktx2.dispose();
    },
  };
}
