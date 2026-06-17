// ============================================================
//  FOREMAN Frontend — lib/cockpit/grid-nav.ts
//  Zweck: Reine Tastatur-Navigation der Heatmap-Matrix (WAI-ARIA-Grid-Muster) bei
//         VARIABLER Spaltenzahl je Zeile (Klassen haben unterschiedlich viele
//         Maschinen). Pfeiltasten bewegen den Fokus geklemmt (kein Umlauf an den
//         Rändern), Pos1/Ende springen an den Zeilenanfang/-rand. Rein → unabhängig
//         von jsdom-SVG-Fokus testbar; die Komponente verdrahtet nur keydown→Fokus.
//  Architektur-Einordnung: View-State (Schicht 2, rein, testbar).
// ============================================================

export type GridKey = "ArrowLeft" | "ArrowRight" | "ArrowUp" | "ArrowDown" | "Home" | "End";

export interface GridPos {
  row: number;
  col: number;
}

const GRID_KEYS: ReadonlySet<string> = new Set<GridKey>([
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Home",
  "End",
]);

/** Ist die Taste eine Raster-Navigationstaste (sonst durchreichen)? */
export function isGridKey(key: string): key is GridKey {
  return GRID_KEYS.has(key);
}

function clamp(value: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, value));
}

/**
 * Berechnet die nächste Fokus-Position in einem Raster mit `rowLengths` Zellen je
 * Zeile. Geklemmt an den Rändern (kein Umlauf). Up/Down halten die Spalte und
 * klemmen auf die Länge der Zielzeile.
 */
export function moveFocus(rowLengths: readonly number[], pos: GridPos, key: GridKey): GridPos {
  const rowCount = rowLengths.length;
  if (rowCount === 0) {
    return pos;
  }
  let row = clamp(pos.row, 0, rowCount - 1);
  const lenHere = Math.max(1, rowLengths[row]!);
  let col = clamp(pos.col, 0, lenHere - 1);

  switch (key) {
    case "ArrowLeft":
      col = clamp(col - 1, 0, lenHere - 1);
      break;
    case "ArrowRight":
      col = clamp(col + 1, 0, lenHere - 1);
      break;
    case "ArrowUp": {
      row = clamp(row - 1, 0, rowCount - 1);
      col = clamp(col, 0, Math.max(0, rowLengths[row]! - 1));
      break;
    }
    case "ArrowDown": {
      row = clamp(row + 1, 0, rowCount - 1);
      col = clamp(col, 0, Math.max(0, rowLengths[row]! - 1));
      break;
    }
    case "Home":
      col = 0;
      break;
    case "End":
      col = lenHere - 1;
      break;
  }

  return { row, col };
}
