// ============================================================
//  FOREMAN Frontend — lib/machine/viewport.ts
//  Zweck: Der Ausschnitt des Sensorverlaufs als reine Rechnung — stufenloses
//         Zoomen und Schieben ohne React, ohne DOM, ohne Timer. Zwei Fenster,
//         die nie verwechselt werden: das LADEFENSTER `[jetzt − hours, jetzt]`
//         bedient allein die Backend-Route (`requiredHours`, Stufenleiter), der
//         AUSSCHNITT lebt im Client und ist eine Teilmenge davon. Zoomen und
//         Schieben rechnen ausschließlich auf schon geholten Punkten.
//         Ob der Ausschnitt dem Live-Rand folgt, ist KEIN Feld, sondern wird in
//         `clampViewport` aus dem rechten Rand abgeleitet — gegen den Fall
//         „sieht aus wie jetzt und ist es nicht", der entsteht, wenn irgendein
//         Pfad ein Folge-Flag zu setzen vergisst.
//  Architektur-Einordnung: View-State (Schicht 2, rein, ohne UI testbar).
// ============================================================
import {
  BUCKET_MS,
  MAX_BACKEND_HOURS,
  RETENTION_HOURS,
  TIME_WINDOWS,
  timeWindow,
} from "./time-window";

import type { TimeWindowId } from "./time-window";

/** Ausschnitt, der am Live-Rand klebt: der rechte Rand IST `jetzt`. */
export interface FollowViewport {
  readonly mode: "follow";
  readonly spanMs: number;
}

/** Stehender Ausschnitt mit absoluten Grenzen — er altert sichtbar weiter. */
export interface FrozenViewport {
  readonly mode: "frozen";
  readonly startMs: number;
  readonly endMs: number;
}

/**
 * Der sichtbare Ausschnitt. Es gibt keinen dritten Zustand und kein Feld
 * daneben (kein `windowId`, kein `follow`-Flag): der Modus folgt aus dem
 * rechten Rand, die gedrückte Schnellwahl wird über `matchPreset` zurückgelesen.
 */
export type TrendViewport = FollowViewport | FrozenViewport;

/** Der zu Epochen aufgelöste Ausschnitt — das, was das Diagramm zeichnet. */
export interface ResolvedViewport {
  readonly startMs: number;
  readonly endMs: number;
}

/** Eine Stunde in ms, aus der Bucket-Breite abgeleitet (keine zweite Zahl). */
export const HOUR_MS = 60 * BUCKET_MS;

/** Ein Tag in ms — nur für die deutsche Spannen-Beschriftung. */
const DAY_MS = 24 * HOUR_MS;

/**
 * Feinster Ausschnitt (20 Minuten). Bei rund 658 px Plotbreite liegen dann ~33 px
 * auf einem Minuten-Bucket: die Punktreihe IST dort das Bild. Darunter vergrößert
 * man nur noch das Raster, denn der Speicher verdichtet nicht nach Spanne.
 */
export const MIN_SPAN_MS = 20 * BUCKET_MS;

/** Weitester Ausschnitt: so tief, wie die Trend-Route zurückreicht. */
export const MAX_SPAN_MS = RETENTION_HOURS * HOUR_MS;

/**
 * Fangzone am Live-Rand als ANTEIL der Spanne — ein Bruchteil der Spanne ist eine
 * konstante Pixelbreite. Eine feste Zeittoleranz wäre bei Wochenspanne kleiner als
 * das Daumenzittern und würde ein Streifen beim Seiten-Scrollen zum Einfrieren machen.
 */
export const LIVE_SNAP_FRACTION = 0.02;

/**
 * Sprossen der Abruf-Leiter (Stunden). Die Leiter ersetzt eine Entprellung: viele
 * Jetzt-Werte innerhalb derselben Minute ergeben denselben `hours`-Wert, und das
 * ist als Gleichheit von Zahlen belegbar statt nur mit Fake-Timern.
 * Letzte Sprosse ist der Deckel der Route.
 */
export const HOURS_LADDER: readonly number[] = [1, 2, 4, 8, 12, 24, 48, 72, 120, MAX_BACKEND_HOURS];

/** Vorlauf beim Abruf: es wird 20 % mehr Verlauf geholt, als der Ausschnitt zeigt. */
export const PRELOAD_FACTOR = 1.2;

/** Ab dieser Pixelbreite je Bucket zeichnet das Diagramm Punkte + Min-Max-Hülle. */
export const DOT_MIN_PX_PER_BUCKET = 6;

// Das Loch-Kriterium steht BEWUSST NICHT hier, sondern als `DEFAULT_MAX_GAP_MS`
// in `trend-series.ts` — dort, wo die Messwerte liegen, gegen die es gilt. Es hier
// ein zweites Mal zu fuehren waere dieselbe Zahl an zwei Orten: Sie laufen
// auseinander, sobald eine von beiden angefasst wird, und beide sehen richtig aus.

/** Spanne auf [MIN, MAX] klemmen. */
function clampSpan(spanMs: number): number {
  return Math.min(MAX_SPAN_MS, Math.max(MIN_SPAN_MS, spanMs));
}

/** Ankeranteil auf [0, 1] klemmen (0 = linker Rand, 1 = rechter Rand). */
function clampFraction(fraction: number): number {
  return Math.min(1, Math.max(0, fraction));
}

/** Zahl mit deutschem Singular/Plural. */
function plural(value: number, one: string, many: string): string {
  return `${value} ${value === 1 ? one : many}`;
}

/**
 * Breite der Fangzone am Live-Rand. Der Boden von einer Bucket-Breite verhindert
 * eine Fangzone unterhalb der Auflösung (2 % von 20 Minuten wären 24 Sekunden).
 */
export function snapMs(spanMs: number): number {
  return Math.max(BUCKET_MS, LIVE_SNAP_FRACTION * spanMs);
}

/** Beginn des über diese Ansicht abrufbaren Verlaufs (die 7-Tage-Wand). */
export function retentionFromMs(nowMs: number): number {
  return nowMs - MAX_SPAN_MS;
}

/** Löst den Ausschnitt zu absoluten Epochen auf. */
export function resolveViewport(viewport: TrendViewport, nowMs: number): ResolvedViewport {
  if (viewport.mode === "follow") {
    return { startMs: nowMs - viewport.spanMs, endMs: nowMs };
  }
  return { startMs: viewport.startMs, endMs: viewport.endMs };
}

/**
 * Bringt ein beliebiges Grenzenpaar in einen gültigen Ausschnitt — in genau
 * dieser Reihenfolge:
 *   (a) Spanne auf [MIN_SPAN_MS, MAX_SPAN_MS] klemmen, verankert am rechten Rand;
 *   (b) liegt der rechte Rand hinter `jetzt`, wandert das GANZE Fenster nach links
 *       (die Spanne bleibt — sonst würde das Bild am Live-Rand stillschweigend
 *       feiner, obwohl niemand gezoomt hat);
 *   (c) liegt der linke Rand vor der 7-Tage-Wand, wandert das GANZE Fenster nach
 *       rechts (dieselbe Zusicherung am anderen Anschlag);
 *   (d) der Modus wird aus dem Abstand zum Live-Rand ABGELEITET.
 * Weil (b) den rechten Rand nie über `jetzt` hinaus lässt und (c) höchstens um
 * `MAX_SPAN_MS − Spanne` nach rechts schiebt, kann (c) das Fenster nicht wieder
 * hinter `jetzt` schieben.
 */
export function clampViewport(startMs: number, endMs: number, nowMs: number): TrendViewport {
  // (a) Spanne klemmen, verankert am rechten Rand.
  const span = clampSpan(endMs - startMs);
  let right = endMs;
  let left = right - span;

  // (b) Hinter dem Jetzt gibt es nichts zu sehen: ganzes Fenster nach links.
  if (right > nowMs) {
    right = nowMs;
    left = right - span;
  }

  // (c) Vor der Wand liegt über diese Ansicht kein Verlauf: ganzes Fenster nach rechts.
  const wall = retentionFromMs(nowMs);
  if (left < wall) {
    left = wall;
    right = left + span;
  }

  // (d) Der Modus ist abgeleitet, nicht gesetzt.
  const clampedSpan = right - left;
  if (nowMs - right <= snapMs(clampedSpan)) {
    return { mode: "follow", spanMs: clampedSpan };
  }
  return { mode: "frozen", startMs: left, endMs: right };
}

/**
 * Schiebt den Ausschnitt um einen Anteil seiner eigenen Spanne.
 * VORZEICHEN: positiv = in Richtung Live-Rand (neuer), negativ = in die
 * Vergangenheit (älter). Eine Zeigergeste nach rechts zieht den Inhalt nach
 * rechts und damit den Ausschnitt in die Vergangenheit — der Aufrufer dreht das
 * Vorzeichen, diese Funktion rechnet auf der Zeitachse.
 */
export function panViewport(
  viewport: TrendViewport,
  fraction: number,
  nowMs: number,
): TrendViewport {
  const { startMs, endMs } = resolveViewport(viewport, nowMs);
  const deltaMs = (endMs - startMs) * fraction;
  return clampViewport(startMs + deltaMs, endMs + deltaMs, nowMs);
}

/**
 * Zoomt um `factor` (> 1 = hineinzoomen, die Spanne wird kleiner) und hält dabei
 * die Zeit unter `anchorFraction` (0 = linker Rand, 1 = rechter Rand) fest.
 *
 * REIHENFOLGE: Die neue Spanne wird HIER geklemmt, BEVOR `clampViewport` läuft.
 * `clampViewport` verankert am rechten Rand; überließe man ihm den Zoom-Boden,
 * würde die Zeit unter dem Anker am Anschlag wegspringen. Das ist die einzige
 * Reihenfolge-Abhängigkeit dieses Moduls und hat einen eigenen Test.
 */
export function zoomViewport(
  viewport: TrendViewport,
  factor: number,
  anchorFraction: number,
  nowMs: number,
): TrendViewport {
  const { startMs, endMs } = resolveViewport(viewport, nowMs);
  const span = clampSpan(endMs - startMs);
  const anchor = clampFraction(anchorFraction);
  const anchorMs = startMs + span * anchor;

  const nextSpan = clampSpan(span / factor);
  const nextStart = anchorMs - nextSpan * anchor;
  return clampViewport(nextStart, nextStart + nextSpan, nowMs);
}

/**
 * Wie viele Stunden Verlauf die Route liefern muss, damit der Ausschnitt gedeckt
 * ist. Reine Ableitung: der Vertrag der Route (`hours` 1–168) wird hier gehalten
 * und nicht von der aufrufenden Stelle. Aufgerundet auf die nächste Sprosse, damit
 * ein wanderndes `jetzt` nicht bei jedem Bild eine neue Anfrage auslöst.
 * `previousHours` ist der zuletzt von dieser Funktion gelieferte Wert; der
 * Rückgabewert unterschreitet ihn nie (das Ladefenster schrumpft nicht unter der
 * Hand, sonst fiele bereits gezeichneter Verlauf wieder heraus).
 */
export function requiredHours(viewport: TrendViewport, nowMs: number, previousHours = 0): number {
  const { startMs } = resolveViewport(viewport, nowMs);
  const neededHours = ((nowMs - startMs) / HOUR_MS) * PRELOAD_FACTOR;
  const rung = HOURS_LADDER.find((hours) => hours >= neededHours) ?? MAX_BACKEND_HOURS;
  return Math.max(previousHours, rung);
}

/** Der Ausschnitt einer Schnellwahl: sie startet immer am Live-Rand. */
export function presetViewport(id: TimeWindowId): TrendViewport {
  return { mode: "follow", spanMs: clampSpan(timeWindow(id).hours * HOUR_MS) };
}

/**
 * Liest zurück, welche Schnellwahl zum Ausschnitt passt — `null` für einen frei
 * gezoomten Ausschnitt. Der gedrückte Zustand wird nirgends gespeichert: ein
 * gedrückter „Tag"-Knopf über einem 2-Stunden-Bild wäre eine Falschaussage im
 * Bedienelement selbst.
 */
export function matchPreset(viewport: TrendViewport, nowMs: number): TimeWindowId | null {
  const { startMs, endMs } = resolveViewport(viewport, nowMs);
  const normalized = clampViewport(startMs, endMs, nowMs);
  if (normalized.mode !== "follow") {
    return null;
  }
  const match = TIME_WINDOWS.find(
    (window) => clampSpan(window.hours * HOUR_MS) === normalized.spanMs,
  );
  return match?.id ?? null;
}

/** Eine Zeitspanne in Worten: „45 Minuten", „2 Stunden 30 Minuten", „3 Tage 4 Stunden". */
export function describeSpan(spanMs: number): string {
  const rounded = Math.max(0, Math.round(spanMs / BUCKET_MS)) * BUCKET_MS;
  const days = Math.floor(rounded / DAY_MS);
  const hours = Math.floor((rounded % DAY_MS) / HOUR_MS);
  const minutes = Math.floor((rounded % HOUR_MS) / BUCKET_MS);

  if (days > 0) {
    const dayText = plural(days, "Tag", "Tage");
    return hours > 0 ? `${dayText} ${plural(hours, "Stunde", "Stunden")}` : dayText;
  }
  if (hours > 0) {
    const hourText = plural(hours, "Stunde", "Stunden");
    return minutes > 0 ? `${hourText} ${plural(minutes, "Minute", "Minuten")}` : hourText;
  }
  return plural(minutes, "Minute", "Minuten");
}

/** Der Ausschnitt in einem Satz — Vorlage für Ansage und Statuszeile. */
export function describeViewport(viewport: TrendViewport, nowMs: number): string {
  const { startMs, endMs } = resolveViewport(viewport, nowMs);
  const spanText = describeSpan(endMs - startMs);
  if (viewport.mode === "follow") {
    return `Ausschnitt ${spanText} bis jetzt, folgt dem Live-Rand`;
  }
  return `Ausschnitt ${spanText}, steht fest, ${describeSpan(nowMs - endMs)} hinter dem Live-Rand`;
}

/** Am Zoom-Boden angekommen (feinste sinnvolle Spanne). */
export function isAtFloor(viewport: TrendViewport, nowMs: number): boolean {
  const { startMs, endMs } = resolveViewport(viewport, nowMs);
  return endMs - startMs <= MIN_SPAN_MS;
}

/** An der 7-Tage-Wand angekommen (weiter zurück liefert diese Ansicht nichts). */
export function isAtWall(viewport: TrendViewport, nowMs: number): boolean {
  return resolveViewport(viewport, nowMs).startMs <= retentionFromMs(nowMs);
}
