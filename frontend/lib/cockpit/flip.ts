// ============================================================
//  FOREMAN Frontend — lib/cockpit/flip.ts
//  Zweck: Erkennt den Kipp-Moment einer Zelle (§4A/§5.6): „eine Zelle, die in Drift
//         kippt, pulst einmal kurz auf und bleibt dann farbig stehen (kein Dauer-
//         blinken)". Rein: vergleicht den vorigen Zell-Zustand mit dem aktuellen und
//         liefert die Maschinen-IDs, die NEU in eine Abweichung gekippt sind. Der
//         View triggert daraus den einmaligen .state-flip (reduced-motion-fest).
//  Architektur-Einordnung: View-State (Schicht 2, rein, testbar).
// ============================================================
import type { CellKind, HeatmapCell } from "./types";

/** War die Zelle vorher auffällig? (für die Kipp-Erkennung). */
function wasDeviating(kind: CellKind | undefined): boolean {
  return kind === "drift" || kind === "warning";
}

/**
 * Liefert die Maschinen-IDs, deren Zelle NEU in eine Abweichung gekippt ist
 * (vorher ruhig/unbekannt → jetzt drift oder warning). Beim ersten Aufbau (leere
 * Vorgeschichte) kippt NICHTS — das Cockpit pulst nicht beim Öffnen, nur bei echten
 * Live-Übergängen.
 */
export function detectKipps(
  previous: ReadonlyMap<number, CellKind>,
  cells: readonly HeatmapCell[],
): Set<number> {
  const kipped = new Set<number>();
  if (previous.size === 0) {
    return kipped;
  }
  for (const cell of cells) {
    const before = previous.get(cell.machineId);
    if (before === undefined) {
      continue; // neue Maschine im Bild → kein Kipp (kein „aus dem Nichts"-Puls)
    }
    if (!wasDeviating(before) && (cell.kind === "drift" || cell.kind === "warning")) {
      kipped.add(cell.machineId);
    }
  }
  return kipped;
}

/** Baut die Zell-Zustands-Karte (Maschinen-ID → Art) für den nächsten Vergleich. */
export function snapshotKinds(cells: readonly HeatmapCell[]): Map<number, CellKind> {
  const map = new Map<number, CellKind>();
  for (const cell of cells) {
    map.set(cell.machineId, cell.kind);
  }
  return map;
}
