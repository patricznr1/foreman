// ============================================================
//  FOREMAN Frontend — lib/machine/geometry.ts
//  Zweck: Reine SVG-Geometrie des TimeSeriesChart — lineare Skalen (Zeit→x,
//         Wert→y) und Pfad-Bau. Ohne DOM/Transport, deterministisch testbar.
//         Die Achsen-Domäne wird vom gewählten Zeitfenster gesetzt (nicht von den
//         Daten) → der Live-Rand wächst rein, ohne dass die Achse springt.
//  Architektur-Einordnung: View-State/Render-Helfer (Schicht 2, rein).
// ============================================================

/** Ein Punkt in SVG-Koordinaten (Pixel). */
export interface Point {
  x: number;
  y: number;
}

/**
 * Lineare Skala domain→range. Invertierter Bereich (range[0] > range[1]) bildet die
 * Y-Achse ab (großer Wert → kleines y). Entartete Domäne (min == max) → Bereichsmitte
 * statt Division durch null (kein NaN), damit eine flache/leere Reihe nicht bricht.
 */
export function scaleLinear(
  domain: [number, number],
  range: [number, number],
): (value: number) => number {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0;
  if (span === 0) {
    const mid = (r0 + r1) / 2;
    return () => mid;
  }
  return (value) => r0 + ((value - d0) / span) * (r1 - r0);
}

/** Baut einen offenen SVG-Pfad (M … L … L …) aus bereits skalierten Pixel-Punkten. */
export function linePath(points: readonly Point[]): string {
  if (points.length === 0) {
    return "";
  }
  return points.map((p, index) => `${index === 0 ? "M" : "L"}${p.x},${p.y}`).join("");
}
