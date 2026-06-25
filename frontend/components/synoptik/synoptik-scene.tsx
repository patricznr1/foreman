// ============================================================
//  FOREMAN Frontend — components/synoptik/synoptik-scene.tsx
//  Zweck: Der Three.js-Renderer der Live-3D-Linie. Baut die Szene EINMAL aus dem
//         (reinen) Linien-Layout, hält EINE geteilte Beleuchtung (Render-Kohärenz),
//         färbt Maschinen bei WS-Updates IN-PLACE um (kein Neuaufbau), und führt
//         Klick/Hover per Raycaster auf machine_id → onSelectMachine (loser Vertrag
//         zur kanonischen Karte). Fehlt WebGL, degradiert die Sicht ehrlich (die
//         barrierefreie Maschinenliste der Sicht bleibt nutzbar). Die GLB-Swap-Naht
//         ist verdrahtet, heute aber ruhend (Manifest liefert nur Platzhalter).
//  Architektur-Einordnung: Sicht-Renderer (Schicht 3, nur Browser, nicht SSR).
// ============================================================
"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import type { MachineStatus } from "@/lib/api/contracts";
import { type ModelSource, resolveModelSource } from "@/lib/synoptic3d/manifest";
import type { MachinePlacement } from "@/lib/synoptic3d/types";
import { cx } from "@/lib/ui/cx";

import { type StatusColors, readStatusColors } from "./scene/colors";
import { type FloorHandle, buildFloor } from "./scene/floor";
import { placeGlb } from "./scene/glb";
import { type LightingHandle, setupLighting } from "./scene/lighting";
import { type ModelLoader, createModelLoader } from "./scene/loaders";
import { type PlaceholderHandle, buildPlaceholder, disposeObject3D } from "./scene/placeholders";

export interface SynoptikSceneProps {
  placements: MachinePlacement[];
  onSelectMachine: (machineId: number) => void;
  className?: string;
}

interface MachineNode {
  handle: PlaceholderHandle;
  status: MachineStatus;
}

interface HoverState {
  id: number;
  label: string;
  clientX: number;
  clientY: number;
}

/**
 * GLB-Swap: lädt das optimierte Modell, normalisiert es auf die Klassen-Höhe am
 * Boden-Zentrum (placeGlb — die nativen Modelle kommen in verschiedenen Einheiten),
 * setzt es in die Maschinen-Gruppe ein (Platzhalter-Körper verbergen, Status-Beacon
 * bleibt) und registriert die GLB-Meshes als Raycast-Ziele (machineId → der Klick-
 * Vertrag zur kanonischen Karte bleibt erhalten). Gegen Unmount/Rebuild-Race
 * abgesichert: wird die Szene vor dem Laden abgebaut, wird das frische Modell sofort
 * wieder freigegeben statt an eine tote Gruppe gehängt.
 */
async function loadGlbForMachine(
  loader: ModelLoader,
  source: Extract<ModelSource, { kind: "glb" }>,
  placement: MachinePlacement,
  handle: PlaceholderHandle,
  registerPickables: (meshes: THREE.Mesh[]) => void,
  isDisposed: () => boolean,
): Promise<void> {
  let model: THREE.Group;
  try {
    model = await loader.loadGlb(source.url);
  } catch {
    return; // Ladefehler → Platzhalter bleibt stehen (ehrliche Degradation).
  }
  if (isDisposed()) {
    disposeObject3D(model); // Race: Szene schon abgebaut → Modell sofort freigeben.
    return;
  }
  placeGlb(model, placement.proportions.height, source.transform);
  const meshes = handle.attachGlb(model);
  for (const mesh of meshes) {
    mesh.userData.machineId = placement.machineId;
  }
  registerPickables(meshes);
}

export function SynoptikScene({ placements, onSelectMachine, className }: SynoptikSceneProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  // Aktuelle Daten/Callback ohne Stale-Closure (der Build-Effekt läuft nur bei
  // geänderter Maschinen-Menge, Handler lesen stets den frischen Stand).
  const dataRef = useRef({ placements, onSelectMachine });
  dataRef.current = { placements, onSelectMachine };

  const [supported, setSupported] = useState(true);
  const [hover, setHover] = useState<HoverState | null>(null);

  // Schlüssel: Maschinen-MENGE (Neuaufbau) vs. Status-Signatur (nur Umfärben).
  const layoutKey = placements.map((placement) => placement.machineId).join(",");
  const statusKey = placements.map((placement) => `${placement.machineId}:${placement.status}`).join(",");

  // Engine-Kontext für Recolor/Cleanup (außerhalb des React-Renderzyklus).
  const engineRef = useRef<{
    nodes: Map<number, MachineNode>;
    statusColors: StatusColors;
    hoveredId: number | null;
  } | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (container === null) {
      return;
    }
    const placementsNow = dataRef.current.placements;
    // Race-Guard: wird die Szene abgebaut, während ein GLB noch lädt, darf das
    // fertige Modell nicht mehr an die (dann tote) Gruppe gehängt werden.
    let disposed = false;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      // Kein WebGL (z. B. Test/jsdom oder Hardware ohne GPU) → ehrliche Degradation.
      setSupported(false);
      return;
    }
    setSupported(true);

    const width = container.clientWidth || 960;
    const height = container.clientHeight || 520;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height, false);
    const canvas = renderer.domElement;
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.display = "block";
    canvas.style.cursor = "grab";
    canvas.setAttribute("aria-hidden", "true");
    container.appendChild(canvas);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d1117);

    const xValues = placementsNow.map((placement) => placement.position.x);
    const lineLength = xValues.length > 0 ? Math.max(...xValues) - Math.min(...xValues) : 10;

    const camera = new THREE.PerspectiveCamera(48, width / height, 0.1, 500);
    const distance = lineLength * 0.62 + 9;
    camera.position.set(lineLength * 0.28, 6.5, distance);
    camera.lookAt(0, 1, 0);

    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.target.set(0, 1, 0);
    controls.minDistance = 4;
    controls.maxDistance = distance * 2.4;
    controls.maxPolarAngle = Math.PI * 0.49; // nie unter den Hallenboden schwenken
    controls.update();

    const lighting: LightingHandle = setupLighting(scene, renderer);
    const floor: FloorHandle = buildFloor(lineLength + 6);
    scene.add(floor.object);
    const loader: ModelLoader = createModelLoader(renderer); // GLTFLoader + Draco/KTX2/meshopt
    const statusColors = readStatusColors(container);

    const nodes = new Map<number, MachineNode>();
    const pickables: THREE.Mesh[] = [];
    for (const placement of placementsNow) {
      const source = resolveModelSource(placement.machineClass);
      const handle = buildPlaceholder(placement.proportions);
      handle.group.position.set(placement.position.x, placement.position.y, placement.position.z);
      handle.group.userData.machineId = placement.machineId;
      handle.setStatusColor(statusColors[placement.status]);
      for (const mesh of handle.pickTargets) {
        mesh.userData.machineId = placement.machineId;
        pickables.push(mesh);
      }
      scene.add(handle.group);
      nodes.set(placement.machineId, { handle, status: placement.status });
      // Swap-Naht: Manifest-Eintrag entscheidet Platzhalter vs. GLB. Der Platzhalter
      // steht sofort; ein GLB lädt asynchron und ersetzt den Körper, sobald da.
      if (source.kind === "glb") {
        void loadGlbForMachine(
          loader,
          source,
          placement,
          handle,
          (meshes) => pickables.push(...meshes),
          () => disposed,
        );
      }
    }

    const engine = { nodes, statusColors, hoveredId: null as number | null };
    engineRef.current = engine;

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    // Klick von Kamera-Drag trennen: Position bei pointerdown merken, beim Klick die
    // zurückgelegte Distanz prüfen (eine OrbitControls-Rotation darf nicht selektieren).
    const DRAG_THRESHOLD_PX = 6;
    let pointerDownAt: { x: number; y: number } | null = null;

    const updatePointer = (event: MouseEvent): boolean => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) {
        return false;
      }
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      return true;
    };

    const pickMachineId = (): number | null => {
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(pickables, false);
      const first = hits[0];
      if (first === undefined) {
        return null;
      }
      const raw: unknown = first.object.userData.machineId;
      return typeof raw === "number" ? raw : null;
    };

    const handlePointerDown = (event: PointerEvent): void => {
      pointerDownAt = { x: event.clientX, y: event.clientY };
    };

    const handleClick = (event: MouseEvent): void => {
      const down = pointerDownAt;
      pointerDownAt = null;
      if (down !== null) {
        const dx = event.clientX - down.x;
        const dy = event.clientY - down.y;
        if (dx * dx + dy * dy > DRAG_THRESHOLD_PX * DRAG_THRESHOLD_PX) {
          return; // war ein Kamera-Drag, kein echter Klick → nicht selektieren
        }
      }
      if (!updatePointer(event)) {
        return;
      }
      const id = pickMachineId();
      if (id !== null) {
        dataRef.current.onSelectMachine(id);
      }
    };

    const handleMove = (event: PointerEvent): void => {
      if (!updatePointer(event)) {
        return;
      }
      const id = pickMachineId();
      if (id !== engine.hoveredId) {
        if (engine.hoveredId !== null) {
          engine.nodes.get(engine.hoveredId)?.handle.setHighlighted(false);
        }
        if (id !== null) {
          engine.nodes.get(id)?.handle.setHighlighted(true);
        }
        engine.hoveredId = id;
        canvas.style.cursor = id !== null ? "pointer" : "grab";
      }
      if (id !== null) {
        const placement = dataRef.current.placements.find((entry) => entry.machineId === id);
        setHover(
          placement === undefined
            ? null
            : { id, label: placement.label, clientX: event.clientX, clientY: event.clientY },
        );
      } else {
        setHover(null);
      }
    };

    const handleLeave = (): void => {
      if (engine.hoveredId !== null) {
        engine.nodes.get(engine.hoveredId)?.handle.setHighlighted(false);
        engine.hoveredId = null;
      }
      canvas.style.cursor = "grab";
      setHover(null);
    };

    canvas.addEventListener("pointerdown", handlePointerDown);
    canvas.addEventListener("click", handleClick);
    canvas.addEventListener("pointermove", handleMove);
    canvas.addEventListener("pointerleave", handleLeave);

    const resize = (): void => {
      const nextWidth = container.clientWidth || width;
      const nextHeight = container.clientHeight || height;
      renderer.setSize(nextWidth, nextHeight, false);
      camera.aspect = nextWidth / nextHeight;
      camera.updateProjectionMatrix();
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);

    renderer.setAnimationLoop(() => {
      controls.update();
      renderer.render(scene, camera);
    });

    return () => {
      disposed = true; // noch ladende GLBs nicht mehr anhängen (Race)
      renderer.setAnimationLoop(null);
      resizeObserver.disconnect();
      canvas.removeEventListener("pointerdown", handlePointerDown);
      canvas.removeEventListener("click", handleClick);
      canvas.removeEventListener("pointermove", handleMove);
      canvas.removeEventListener("pointerleave", handleLeave);
      controls.dispose();
      for (const node of nodes.values()) {
        node.handle.dispose(); // disposed jetzt auch ein evtl. angehängtes GLB
      }
      floor.dispose();
      lighting.dispose();
      loader.dispose();
      renderer.dispose();
      if (canvas.parentNode === container) {
        container.removeChild(canvas);
      }
      engineRef.current = null;
    };
    // Bewusst nur an der Maschinen-MENGE (layoutKey): Status-Änderungen färben
    // über den Recolor-Effekt in-place um, ohne die Szene neu zu bauen. Handler
    // lesen frische Daten/Callback aus dataRef — daher keine weiteren Deps nötig.
  }, [layoutKey]);

  // Live-Umfärben: bei neuer Status-Signatur die betroffenen Maschinen in-place färben.
  useEffect(() => {
    const engine = engineRef.current;
    if (engine === null) {
      return;
    }
    for (const placement of dataRef.current.placements) {
      const node = engine.nodes.get(placement.machineId);
      if (node === undefined || node.status === placement.status) {
        continue;
      }
      node.handle.setStatusColor(engine.statusColors[placement.status]);
      node.status = placement.status;
    }
  }, [statusKey]);

  return (
    <div className={cx("relative", className)}>
      <div
        ref={containerRef}
        role="img"
        aria-label="3D-Ansicht der Montagelinie 1 (digitaler Zwilling, Simulation)"
        className="h-[58vh] min-h-[26rem] w-full overflow-hidden rounded-lg border border-line-subtle bg-surface-raised"
      />
      {!supported ? (
        <div
          role="status"
          className="absolute inset-0 flex items-center justify-center rounded-lg border border-line-subtle bg-surface-raised p-6 text-center text-body text-note-caveat"
        >
          3D-Ansicht hier nicht verfügbar (WebGL fehlt). Die Maschinenliste unten bleibt nutzbar.
        </div>
      ) : null}
      {hover !== null && supported ? (
        <span
          role="tooltip"
          className="pointer-events-none fixed z-50 rounded-md border border-line-subtle bg-surface-overlay px-2 py-1 text-caption text-fg-primary shadow"
          style={{ left: hover.clientX + 14, top: hover.clientY + 14 }}
        >
          {hover.label}
        </span>
      ) : null}
    </div>
  );
}
