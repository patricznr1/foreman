// ============================================================
//  FOREMAN Frontend — lib/machine/gesture.ts
//  Zweck: Reine Gestenmathematik des Sensor-Verlaufs — Absichtsschwelle,
//         Zerlegung des Zwei-Finger-Griffs in Zoom UND Schub, Anker-Anteil und
//         Doppeltipp. Kein DOM, keine Ereignisse, keine Messung: Rechteck-Maße
//         kommen als ZAHLEN herein, heraus kommen Anteile und Faktoren. So ist
//         jede Schwelle ohne Layout belegbar — die Verdrahtung (Zeiger-Ereignisse,
//         Rechteck-Messung) bleibt allein in trend-viewport-surface.tsx.
//         Die Schwellen sind bewusst grob: bedient wird mit Arbeitshandschuhen.
//  Architektur-Einordnung: View-State/Eingabe-Helfer (Schicht 2, rein).
// ============================================================

/**
 * Ein Zeiger in CLIENT-Koordinaten (Pixel, Ursprung links oben im Sichtfenster).
 * Bewusst NICHT `Point` aus geometry.ts — das sind SVG-Koordinaten der
 * Zeichenfläche. Zwei Bezugssysteme, zwei Namen: sonst rechnet irgendwann jemand
 * einen Fingerpunkt gegen eine SVG-Skala, und das Ergebnis sieht plausibel aus.
 */
export interface PointerPosition {
  x: number;
  y: number;
}

/** Die beiden Zeiger eines Zwei-Finger-Griffs. */
export type PointerPair = readonly [PointerPosition, PointerPosition];

/**
 * Die zwei Absichten eines Zwei-Finger-Griffs, getrennt gemeldet. Erst zoomen
 * (verankert an `anchorFraction`), dann um `panFraction` schieben — in dieser
 * Reihenfolge bleibt die Zeit unter dem Fingerpaar dieselbe.
 */
export interface PinchIntents {
  /** Faktor der Spannen-Änderung; genau 1 innerhalb der Totzone. */
  factor: number;
  /** Anteil 0..1 der Plotbreite, an dem der Zoom verankert wird. */
  anchorFraction: number;
  /** Verschiebung des Fingerpaar-Mittelpunkts als Anteil der Plotbreite. */
  panFraction: number;
}

/**
 * Mindestweg in Pixeln, bevor ein Finger als Schiebe-Absicht gilt. 12 px statt der
 * sonst üblichen 5–8: eine behandschuhte Berührung wackelt beim Aufsetzen mehr als
 * eine nackte Fingerkuppe. Darunter gehört die Bewegung dem Browser (Seitenlauf).
 */
export const INTENT_PX = 12;

/**
 * Um wie viel waagerechter als senkrecht ein Zug sein muss, um als Schieben zu
 * gelten. Ein Streifer beim Seiten-Scrollen ist überwiegend senkrecht; erst das
 * 1,5-fache Übergewicht in der Waagerechten ist eine Aussage statt eines Zitterns.
 */
export const INTENT_RATIO = 1.5;

/**
 * Totzone des Abstandsverhältnisses. Solange es in
 * [1 − PINCH_DEADZONE, 1 + PINCH_DEADZONE] liegt, ist der Zoom-Anteil genau 1.
 * Zwei aufgelegte Knöchel sind zwei Zeiger — ohne Totzone wäre jedes Abstützen
 * mit der Handfläche ein Zoom.
 */
export const PINCH_DEADZONE = 0.1;

/** Längste Pause zwischen zwei Berührungen, die noch als Doppeltipp zählt. */
export const DOUBLE_TAP_MS = 300;

/**
 * Größter Abstand zweier Berührungen, die noch ein Doppeltipp sind. Bewusst 40
 * statt der sonst üblichen 24: mit Arbeitshandschuh landet die zweite Berührung
 * leicht 30 bis 40 px neben der ersten. Eine Schwelle, die dort abreißt, liest
 * sich unter Zeitdruck als kaputter Schirm — und dann wird gehämmert.
 */
export const DOUBLE_TAP_PX = 40;

/** Grenzen der Totzone, aus PINCH_DEADZONE abgeleitet — keine zweiten Zahlen. */
const PINCH_MIN_RATIO = 1 - PINCH_DEADZONE;
const PINCH_MAX_RATIO = 1 + PINCH_DEADZONE;

/**
 * Ist dieser Wert ein Teiler, durch den gerechnet werden darf? Der Fall tritt echt
 * auf: in jsdom liefert jede Rechteck-Messung 0, und zwei Finger können exakt
 * aufeinander liegen. Ohne diese Frage stünde am Ende ein NaN in der Achsen-Domäne
 * — das SVG bliebe still leer, ohne Fehler und ohne Log-Zeile.
 */
function isUsableDivisor(value: number): boolean {
  return Number.isFinite(value) && value > 0;
}

/**
 * Ist dieser Zug eine waagerechte Schiebe-Absicht? Beides muss gelten: genug Weg
 * (> INTENT_PX) UND genug Übergewicht gegenüber der Senkrechten (> INTENT_RATIO).
 * Solange das nicht erfüllt ist, wird der Zeiger nicht gefangen und der senkrechte
 * Seitenlauf bleibt beim Browser. Beide Grenzen sind ausschließend: genau auf der
 * Schwelle ist noch keine Absicht.
 */
export function isHorizontalIntent(dx: number, dy: number): boolean {
  const travelX = Math.abs(dx);
  const travelY = Math.abs(dy);
  return travelX > INTENT_PX && travelX > INTENT_RATIO * travelY;
}

/**
 * Rechnet einen Pixelweg in eine Zeitspanne um. Ohne messbare Breite bewegt die
 * Geste NICHTS (0), statt NaN in die Achsen-Domäne zu schreiben.
 */
export function pixelsToMs(dxPx: number, plotWidthPx: number, spanMs: number): number {
  if (!isUsableDivisor(plotWidthPx)) {
    return 0;
  }
  return (dxPx / plotWidthPx) * spanMs;
}

/**
 * Pixelweg als Anteil der Plotbreite (Vorzeichen bleibt: nach links ist negativ).
 * Derselbe Null-Schutz wie in `pixelsToMs` — ohne Breite kein Anteil, aber auch
 * kein NaN.
 */
export function panFraction(dxPx: number, plotWidthPx: number): number {
  if (!isUsableDivisor(plotWidthPx)) {
    return 0;
  }
  return dxPx / plotWidthPx;
}

/**
 * Wo auf der Zeichenfläche (0 = linker Plotrand, 1 = rechter) liegt `clientX`?
 * Außerhalb wird geklemmt — ein Finger auf der Achsenbeschriftung verankert am
 * Rand statt außerhalb des Bildes. Ohne messbares Rechteck ist die Mitte die
 * Antwort: das ist der neutrale Anker, und er ist endlich.
 */
export function anchorRatio(
  clientX: number,
  rectLeft: number,
  rectWidth: number,
  padLeft: number,
  padRight: number,
): number {
  const plotWidthPx = rectWidth - padLeft - padRight;
  if (!isUsableDivisor(plotWidthPx)) {
    return 0.5;
  }
  const ratio = (clientX - rectLeft - padLeft) / plotWidthPx;
  if (ratio < 0) {
    return 0;
  }
  if (ratio > 1) {
    return 1;
  }
  return ratio;
}

/** Abstand zweier Zeiger in Pixeln. */
export function distance(a: PointerPosition, b: PointerPosition): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/**
 * Zerlegt einen Zwei-Finger-Griff in ZWEI Absichten: das Abstandsverhältnis ergibt
 * den Zoom-Faktor, die Verschiebung des Mittelpunkts den Schub. Weil beide getrennt
 * gemeldet werden, bleibt die Geste am Zoom-Boden lebendig — der Zoom-Anteil ist
 * dort ein Nulldurchgang, der Schub wirkt weiter. Kein Sonderfall im geklemmten
 * Zweig nötig.
 *
 * Verankert wird am STARTMITTELPUNKT: die Wanderung des Mittelpunkts steckt bereits
 * im Schub. Nähme man den aktuellen Mittelpunkt, liefe der Inhalt unter den Fingern
 * doppelt so weit wie die Hand.
 */
export function pinchIntents(
  startPair: PointerPair,
  currentPair: PointerPair,
  rectLeft: number,
  rectWidth: number,
  padLeft: number,
  padRight: number,
): PinchIntents {
  const startDistance = distance(startPair[0], startPair[1]);
  const currentDistance = distance(currentPair[0], currentPair[1]);
  // Zwei Zeiger auf demselben Punkt haben kein Verhältnis — dann eben kein Zoom.
  const ratio = isUsableDivisor(startDistance) ? currentDistance / startDistance : 1;
  const withinDeadzone = ratio >= PINCH_MIN_RATIO && ratio <= PINCH_MAX_RATIO;

  const startMidX = (startPair[0].x + startPair[1].x) / 2;
  const currentMidX = (currentPair[0].x + currentPair[1].x) / 2;

  return {
    factor: withinDeadzone ? 1 : ratio,
    anchorFraction: anchorRatio(startMidX, rectLeft, rectWidth, padLeft, padRight),
    panFraction: panFraction(currentMidX - startMidX, rectWidth - padLeft - padRight),
  };
}

/**
 * Zwei Berührungen dicht genug in Zeit UND Ort, um ein Doppeltipp zu sein.
 * `prevMs === null` heißt: es gab noch keine erste Berührung. Beide Grenzen sind
 * ausschließend, und eine zweite Berührung VOR der ersten (rückwärts gestellte Uhr)
 * ist keine Folge, sondern ein Zufall — sonst würde ein Zeitsprung eine beliebige
 * Berührung zum Doppeltipp erklären.
 */
export function isDoubleTap(
  prevMs: number | null,
  nowMs: number,
  prevX: number,
  x: number,
): boolean {
  if (prevMs === null) {
    return false;
  }
  const elapsedMs = nowMs - prevMs;
  return elapsedMs >= 0 && elapsedMs < DOUBLE_TAP_MS && Math.abs(x - prevX) < DOUBLE_TAP_PX;
}
