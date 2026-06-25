// ============================================================
//  FOREMAN Frontend — lib/machine/grouping.ts
//  Zweck: Reine Gruppierung des Karten-Grids nach Maschinenklasse → Synoptik-Stufe
//         (Fördern/Pressen/Handling/Bestücken/Endkontrolle), in der kanonischen
//         Reihenfolge der Linien-Sequenz. Unbekannte Klassen behalten ihren rohen
//         Namen (kein erfundenes Label) und reihen sich hinter die bekannten Stufen;
//         fehlende Klasse wird ehrlich als „Ohne Klasse" geführt.
//  Architektur-Einordnung: View-State (Schicht 2), ohne UI testbar.
// ============================================================
import type { MachineCardOut } from "@/lib/api/contracts";

// Bekannte Maschinenklassen → Hallensprache-Stufe (Synoptik-Spalten des Twin-Parks).
const STAGE: Record<string, string> = {
  feeder: "Fördern",
  servo_press: "Pressen",
  servo_axis: "Handling",
  robot: "Bestücken",
  vision: "Endkontrolle",
  mixing_unit: "Dosieren",
};

// Kanonische Stufen-Reihenfolge entlang der Linie (Montagelinie 1: Zuführung →
// Pressen → Handling → Bestücken → Endkontrolle). Exportiert als Single Source
// der Linien-Sequenz — auch die 3D-Synoptik ordnet die Maschinen hierüber an.
export const STAGE_ORDER: readonly string[] = [
  "feeder",
  "servo_press",
  "servo_axis",
  "robot",
  "vision",
  "mixing_unit",
];

/** Maschinenklasse → Synoptik-Stufe; unbekannt → roher Name; null → „Ohne Klasse". */
export function stageLabel(machineClass: string | null): string {
  if (machineClass === null) {
    return "Ohne Klasse";
  }
  return STAGE[machineClass] ?? machineClass;
}

export interface StageGroup {
  /** Anzeige-Label der Stufe (Synoptik-Spalte). */
  stage: string;
  machineClass: string | null;
  cards: MachineCardOut[];
}

/**
 * Rang einer Klasse in der kanonischen Linien-Sequenz: bekannt → Index in
 * STAGE_ORDER, unbekannt → hinter die bekannten Stufen, fehlend → ganz nach
 * hinten. Geteilt mit der 3D-Synoptik, damit beide Sichten dieselbe Reihenfolge
 * sprechen (Single Source).
 */
export function stageRank(machineClass: string | null): number {
  if (machineClass === null) {
    return STAGE_ORDER.length + 1; // ohne Klasse ganz nach hinten
  }
  const index = STAGE_ORDER.indexOf(machineClass);
  return index === -1 ? STAGE_ORDER.length : index; // unbekannt zwischen bekannt und null
}

/** Gruppiert die Karten nach Klasse/Stufe in stabiler, kanonischer Reihenfolge. */
export function groupByStage(cards: MachineCardOut[]): StageGroup[] {
  const byClass = new Map<string | null, MachineCardOut[]>();
  for (const card of cards) {
    const existing = byClass.get(card.machine_class);
    if (existing === undefined) {
      byClass.set(card.machine_class, [card]);
    } else {
      existing.push(card);
    }
  }
  return [...byClass.entries()]
    .map(([machineClass, groupCards]) => ({
      stage: stageLabel(machineClass),
      machineClass,
      cards: groupCards,
    }))
    .sort((a, b) => {
      const byRank = stageRank(a.machineClass) - stageRank(b.machineClass);
      return byRank !== 0 ? byRank : a.stage.localeCompare(b.stage, "de");
    });
}
