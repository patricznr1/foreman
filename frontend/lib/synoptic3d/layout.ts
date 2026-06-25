// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/layout.ts
//  Zweck: Ordnet die Maschinen einer Linie als 3D-Sequenz an — primär nach der
//         kanonischen Stufen-Reihenfolge (STAGE_ORDER aus grouping.ts, geteilte
//         Quelle), sekundär nach DB-id (= external-id-Reihenfolge je Klasse, also
//         PR-01 < PR-02 < PR-03). So entsteht die Materialfluss-Richtung
//         (Fördern → Pressen → Handling → Bestücken → Endkontrolle) entlang +x,
//         und eine kranke Maschine steht räumlich zwischen ihren gesunden
//         Schwestern (PR-02 zwischen PR-01/PR-03). Reine Funktion — ohne THREE/DOM
//         testbar; der Renderer konsumiert nur das Ergebnis.
//  Architektur-Einordnung: View-State (Schicht 2), ohne UI testbar.
// ============================================================
import type { MachineStatusOut } from "@/lib/api/contracts";
import { STAGE_ORDER, stageLabel, stageRank } from "@/lib/machine/grouping";
import { proportionsFor } from "./placeholder-proportions";
import type { MachinePlacement } from "./types";

export interface LayoutOptions {
  /** Lücke zwischen Maschinen DERSELBEN Stufe (Kante-zu-Kante, Meter). */
  intraGap?: number;
  /** Zusätzliche Lücke ZWISCHEN zwei Stufen (Kante-zu-Kante, Meter). */
  stageGap?: number;
}

const DEFAULT_INTRA_GAP = 1.2;
const DEFAULT_STAGE_GAP = 2.6;

/**
 * Baut die geordnete Linien-Anordnung. x wächst in Materialflussrichtung, die Linie
 * wird mittig um den Ursprung zentriert (neutrale Kamera/Controls). y = 0 (Boden),
 * z = 0; der Pivot jeder Maschine liegt am Boden-Zentrum.
 */
export function buildLineLayout(
  machines: readonly MachineStatusOut[],
  options: LayoutOptions = {},
): MachinePlacement[] {
  const intraGap = options.intraGap ?? DEFAULT_INTRA_GAP;
  const stageGap = options.stageGap ?? DEFAULT_STAGE_GAP;

  // Stabile Sequenz: Stufe (kanonisch) → Klasse (trennt distinkte Fremdklassen,
  // die sich denselben Rang teilen) → id (Schwester-Reihenfolge je Klasse).
  const sorted = [...machines].sort((a, b) => {
    const byStage = stageRank(a.machine_class) - stageRank(b.machine_class);
    if (byStage !== 0) {
      return byStage;
    }
    const byClass = (a.machine_class ?? "").localeCompare(b.machine_class ?? "", "de");
    return byClass !== 0 ? byClass : a.id - b.id;
  });

  const placements: MachinePlacement[] = [];
  let cursor = 0; // linke Kante der nächsten Maschine entlang +x
  let prevStageKey: string | null = null;
  let stageIndex = -1;
  let indexInStage = -1;

  for (const machine of sorted) {
    const rank = stageRank(machine.machine_class);
    const proportions = proportionsFor(machine.machine_class);
    // Stufen-Identität: bekannte Klassen über ihren Rang, unbekannte über ihren
    // Namen (alle Unbekannten teilen denselben Rang, sind aber eigene Stufen).
    const stageKey =
      rank === STAGE_ORDER.length ? `unknown:${machine.machine_class}` : String(rank);

    if (stageKey !== prevStageKey) {
      // Neue Stufe: Stufen-Lücke (außer am Linienanfang), Stufenzähler weiterdrehen.
      if (prevStageKey !== null) {
        cursor += stageGap;
      }
      stageIndex += 1;
      indexInStage = 0;
      prevStageKey = stageKey;
    } else {
      cursor += intraGap;
      indexInStage += 1;
    }

    const centerX = cursor + proportions.width / 2;
    placements.push({
      machineId: machine.id,
      label: machine.label,
      machineClass: machine.machine_class,
      stage: stageLabel(machine.machine_class),
      status: machine.status,
      position: { x: centerX, y: 0, z: 0 },
      proportions,
      stageIndex,
      indexInStage,
    });
    cursor += proportions.width; // rechte Kante = Startpunkt der nächsten Lücke
  }

  // Gesamtlänge bekannt → mittig zentrieren (relative Abstände bleiben erhalten).
  const shift = cursor / 2;
  for (const placement of placements) {
    placement.position.x -= shift;
  }
  return placements;
}
