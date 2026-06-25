// ============================================================
//  FOREMAN Frontend — components/synoptik/scene/glb.test.ts
//  Zweck: Prüft die GLB-Renderer-Logik ohne WebGL (THREE-Objekte laufen in jsdom):
//         Normalisierung auf Klassen-Höhe am Boden-Zentrum (placeGlb), Einsetzen
//         ins Handle (Platzhalter-Körper verbergen, GLB-Meshes als Pick-Ziele
//         zurückgeben) und vollständiges Freigeben beim Dispose.
// ============================================================
import * as THREE from "three";
import { describe, expect, it, vi } from "vitest";

import { IDENTITY_TRANSFORM } from "@/lib/synoptic3d/manifest";
import { proportionsFor } from "@/lib/synoptic3d/placeholder-proportions";

import { placeGlb } from "./glb";
import { buildPlaceholder, disposeObject3D } from "./placeholders";

/** Fake-GLB: eine um den Ursprung zentrierte Box mit `heightUnits` Höhe (nicht boden-verankert). */
function fakeGlb(heightUnits: number): THREE.Group {
  const group = new THREE.Group();
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(50, heightUnits, 30),
    new THREE.MeshStandardMaterial(),
  );
  group.add(mesh);
  return group;
}

describe("placeGlb", () => {
  it("skaliert auf die Klassen-Höhe und verankert am Boden-Zentrum", () => {
    const model = fakeGlb(200);
    placeGlb(model, 2.6, IDENTITY_TRANSFORM);
    model.updateMatrixWorld(true);

    const box = new THREE.Box3().setFromObject(model);
    expect(box.min.y).toBeCloseTo(0, 5); // steht auf dem Boden
    expect(box.max.y - box.min.y).toBeCloseTo(2.6, 5); // auf Zielhöhe skaliert
    expect((box.min.x + box.max.x) / 2).toBeCloseTo(0, 5); // x mittig
    expect((box.min.z + box.max.z) / 2).toBeCloseTo(0, 5); // z mittig
  });
});

describe("PlaceholderHandle.attachGlb", () => {
  it("verbirgt die Platzhalter-Körper, hängt das GLB ein und gibt seine Meshes zurück", () => {
    const handle = buildPlaceholder(proportionsFor("servo_press"));
    const model = fakeGlb(200);

    const meshes = handle.attachGlb(model);

    expect(meshes.length).toBeGreaterThan(0); // → werden als Raycast-Ziele registriert
    expect(handle.group.children).toContain(model);
    const bodies = handle.pickTargets.filter((m) => m.userData.isPlaceholderBody === true);
    expect(bodies.length).toBeGreaterThan(0);
    for (const body of bodies) {
      expect(body.visible).toBe(false);
    }
  });

  it("gibt beim Dispose auch das eingesetzte GLB frei (Geometrie + Material)", () => {
    const handle = buildPlaceholder(proportionsFor("robot"));
    const model = fakeGlb(10);
    const mesh = model.children[0] as THREE.Mesh;
    const geometrySpy = vi.spyOn(mesh.geometry, "dispose");
    const materialSpy = vi.spyOn(mesh.material as THREE.Material, "dispose");

    handle.attachGlb(model);
    handle.dispose();

    expect(geometrySpy).toHaveBeenCalled();
    expect(materialSpy).toHaveBeenCalled();
  });
});

describe("disposeObject3D", () => {
  it("traversiert den Teilbaum und gibt jedes Mesh frei", () => {
    const root = fakeGlb(5);
    const mesh = root.children[0] as THREE.Mesh;
    const geometrySpy = vi.spyOn(mesh.geometry, "dispose");

    disposeObject3D(root);

    expect(geometrySpy).toHaveBeenCalledTimes(1);
  });
});
