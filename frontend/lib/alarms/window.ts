// ============================================================
//  FOREMAN Frontend — lib/alarms/window.ts
//  Zweck: Virtualisierungs-Mathematik (Studie §5.1: „nur Sichtbares im DOM"). Reine
//         Funktion über uniformer Slot-Höhe — kein DOM, keine Lib, ohne UI testbar.
//         Die `AlarmList` virtualisiert über die flache VisualRow-Folge: aus
//         Scroll-Offset + Viewport ergibt sich das sichtbare Fenster + die Polster.
//  Architektur-Einordnung: Reine Ableitung (Schicht 2). Ohne UI/Lib testbar.
// ============================================================

export interface WindowInput {
  scrollTop: number;
  viewportHeight: number;
  rowHeight: number;
  count: number;
  /** Zusätzliche Zeilen ober-/unterhalb (ruckelfreies Scrollen). Default 4. */
  overscan?: number;
}

export interface WindowRange {
  /** Erster zu rendernder Index (inklusiv). */
  startIndex: number;
  /** Erster NICHT mehr zu rendernder Index (exklusiv). */
  endIndex: number;
  /** Polster oberhalb (px), hält die Scroll-Position stabil (kein Sprung). */
  paddingTop: number;
  /** Polster unterhalb (px). */
  paddingBottom: number;
  /** Gesamthöhe aller Slots (px) — für die Scrollbar-Geometrie. */
  totalHeight: number;
}

export function windowRange(input: WindowInput): WindowRange {
  const { scrollTop, viewportHeight, rowHeight, count } = input;
  const overscan = input.overscan ?? 4;
  const safeCount = Math.max(0, Math.floor(count));
  const totalHeight = safeCount * Math.max(0, rowHeight);

  if (safeCount === 0 || rowHeight <= 0 || viewportHeight <= 0) {
    return { startIndex: 0, endIndex: 0, paddingTop: 0, paddingBottom: 0, totalHeight };
  }

  const clampedScroll = Math.min(Math.max(0, scrollTop), totalHeight);
  const firstVisible = Math.floor(clampedScroll / rowHeight);
  const visibleCount = Math.ceil(viewportHeight / rowHeight);

  const startIndex = Math.max(0, firstVisible - overscan);
  const endIndex = Math.min(safeCount, firstVisible + visibleCount + overscan);

  const paddingTop = startIndex * rowHeight;
  const paddingBottom = (safeCount - endIndex) * rowHeight;

  return { startIndex, endIndex, paddingTop, paddingBottom, totalHeight };
}
