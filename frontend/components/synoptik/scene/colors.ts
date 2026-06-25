// ============================================================
//  FOREMAN Frontend — components/synoptik/scene/colors.ts
//  Zweck: Löst die Status-Farb-Token (--color-state-*) zur Laufzeit über ein
//         Probe-Element zu THREE-Farben auf. Browsers normalisieren die var()-Kette
//         beim Auslesen von `color` zu rgb(...) — so bleibt die 3D-Palette an die
//         Design-Token gekoppelt (theme-fest, eine Quelle), statt hartkodiert.
//  Architektur-Einordnung: Renderer-Adapter (Schicht 3, nur Browser).
// ============================================================
import * as THREE from "three";

import type { MachineStatus } from "@/lib/api/contracts";
import { statusColorVar } from "@/lib/synoptic3d/status-color";

export type StatusColors = Record<MachineStatus, THREE.Color>;

const FALLBACK_HEX = "#8892a0";

/**
 * Liest die aufgelösten Status-Farben aus den CSS-Tokens als THREE-Farben.
 * THREE.Color.setStyle interpretiert rgb(...) als sRGB und überführt es in den
 * linearen Arbeitsraum (passend zu ACESFilmic-Tonemapping + sRGB-Ausgabe).
 */
export function readStatusColors(root: HTMLElement): StatusColors {
  const probe = document.createElement("span");
  probe.style.display = "none";
  root.appendChild(probe);

  const resolve = (status: MachineStatus): THREE.Color => {
    probe.style.color = `var(${statusColorVar(status)})`;
    const computed = getComputedStyle(probe).color;
    const color = new THREE.Color();
    try {
      color.setStyle(computed.length > 0 ? computed : FALLBACK_HEX);
    } catch {
      color.setStyle(FALLBACK_HEX);
    }
    return color;
  };

  const colors: StatusColors = {
    healthy: resolve("healthy"),
    drift_active: resolve("drift_active"),
    open_warning: resolve("open_warning"),
    critical: resolve("critical"),
  };

  root.removeChild(probe);
  return colors;
}
