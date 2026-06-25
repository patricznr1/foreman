// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/status-color.ts
//  Zweck: Komponierter Maschinenstatus → FCSM-Zustand (NE 107) → Name der
//         Status-Farb-Custom-Property (--color-state-*). EINZIGE Wahrheit der
//         3D-Status-Farbe: dieselbe Tabelle (MACHINE_STATUS_TO_FCSM) und dieselben
//         Token (FCSM_TOKEN) wie Cockpit/Heatmap/Karte — die 3D-Linie erfindet
//         keine eigene Palette. Der Renderer löst die Property zur Laufzeit zu
//         einer THREE-Farbe auf; diese Schicht bleibt THREE-/DOM-frei und testbar.
//  Architektur-Einordnung: View-State (Schicht 2), ohne UI testbar.
// ============================================================
import type { MachineStatus } from "@/lib/api/contracts";
import { FCSM_TOKEN, MACHINE_STATUS_TO_FCSM, type Fcsm } from "@/lib/ui/wording";

/** Komponierter Status → FCSM-Zustand (ruhige Rampe ok → S → C). */
export function statusFcsm(status: MachineStatus): Fcsm {
  return MACHINE_STATUS_TO_FCSM[status];
}

/**
 * Komponierter Status → Name der CSS-Custom-Property der Status-Farbe
 * (z. B. „--color-state-ok"). Der Renderer liest diese Property über ein
 * Probe-Element aus und übersetzt sie in eine THREE-Farbe — so bleibt die Palette
 * an die Design-Token gekoppelt (eine Quelle, theme-fest), nicht hartkodiert.
 */
export function statusColorVar(status: MachineStatus): string {
  return `--color-${FCSM_TOKEN[statusFcsm(status)]}`;
}
