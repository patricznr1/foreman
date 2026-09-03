// ============================================================
//  FOREMAN Frontend — components/machine/trend-viewport-surface.tsx
//  Zweck: Die Gestenfläche über dem Sensortrend — die EINZIGE Stelle des Vorhabens
//         mit Rechteck-Messung, Zeiger-Fang und Ereignis-Verdrahtung. Sie hält
//         KEINEN Zustand und rechnet NICHT: jede Umrechnung von Pixeln in Anteile
//         geht durch lib/machine/gesture.ts, jede Aussage über den Ausschnitt durch
//         lib/machine/viewport.ts. Nach oben gemeldet werden nur Absichten
//         (Bruchteil, Faktor) — angewendet werden sie in der Detailsicht, damit
//         gestapelte Panels eine gemeinsame Zeitachse behalten.
//         Gebaut gegen das Kapern der Seite: `touch-action: pan-y` gibt allein die
//         Waagerechte ab, ein Finger schiebt erst nach nachgewiesener Absicht, und
//         `preventDefault()` fällt ausschließlich im Zwei-Finger-touchmove und im
//         Strg/Cmd-Rad-Zweig. Bild-auf, Bild-ab, Leertaste und Escape bleiben
//         unangetastet — sie sind der Weg dessen, der keinen anderen durch die
//         Seite hat.
//  Architektur-Einordnung: Sicht-Baustein/Eingabe (Schicht 3, client).
// ============================================================
"use client";

import { useCallback, useEffect, useRef } from "react";
import type {
  KeyboardEvent as ReactKeyboardEvent,
  PointerEvent as ReactPointerEvent,
  ReactNode,
} from "react";

import {
  anchorRatio,
  isDoubleTap,
  isHorizontalIntent,
  panFraction,
  pinchIntents,
} from "@/lib/machine/gesture";
import type { PointerPair, PointerPosition } from "@/lib/machine/gesture";
import { MAX_SPAN_MS, MIN_SPAN_MS, describeViewport } from "@/lib/machine/viewport";
import type { TrendViewport } from "@/lib/machine/viewport";

export interface TrendViewportSurfaceProps {
  /** Der aktuelle Ausschnitt — hier nur für die Beschriftung der Trefferfläche. */
  viewport: TrendViewport;
  /** Der Live-Rand, von der Detailsicht durchgereicht (nie selbst geholt). */
  nowMs: number;
  /**
   * Schub als Anteil der Spanne, im VORZEICHEN DER ZEITACHSE: positiv = Richtung
   * Live-Rand (neuer), negativ = in die Vergangenheit. Ein Zug nach rechts zieht
   * den Inhalt nach rechts und damit den Ausschnitt in die Vergangenheit — diese
   * Fläche dreht das Vorzeichen der Zeigergeste deshalb genau einmal, hier an der
   * Grenze, und nicht irgendwo weiter oben ein zweites Mal.
   */
  onPan: (fraction: number) => void;
  /** Zoom: Faktor > 1 zoomt hinein, verankert an `anchorFraction` (0..1). */
  onZoom: (factor: number, anchorFraction: number) => void;
  /** Ende einer Geste — der einzige Anlass für eine neue Ansage. */
  onGestureEnd: () => void;
  /**
   * Test-/Override-Hook: feste Breite der Gestenfläche in Pixeln (Bauform von
   * `viewportHeight` in components/alarms/alarm-list.tsx). In jsdom misst
   * `getBoundingClientRect` immer 0; ohne diese Einspritzung wäre der ganze
   * Gestenpfad unprüfbar, weil jede Umrechnung folgerichtig 0 lieferte.
   */
  surfaceWidthPx?: number;
  children: ReactNode;
}

/** Der Ein-Finger-Zug zwischen Aufsetzen und Loslassen. */
interface DragState {
  pointerId: number;
  startX: number;
  startY: number;
  /** Zuletzt GEMELDETE Stelle — der Bezug für den nächsten Schritt. */
  lastX: number;
  /** Absicht nachgewiesen? Davor gehört die Bewegung dem Browser. */
  panning: boolean;
}

/**
 * Der Zwei-Finger-Griff hat ZWEI Bezugspaare, und das ist eine Entscheidung, keine
 * Verdopplung: `pinchIntents` beschreibt die Strecke vom Bezugspaar zum aktuellen
 * Paar ABSOLUT. Meldete man bei jedem Ereignis die Strecke seit Gestenbeginn und
 * wendete sie jedes Mal an, potenzierte sich der Zoom (aus 1,5 · 2,0 würde 3 statt
 * 2). Gemeldet werden deshalb SCHRITTE, und dafür wird das Bezugspaar nach jeder
 * Meldung nachgezogen.
 *
 * Warum trotzdem zwei Paare: Zöge man den Zoom-Bezug auch bei einem reinen Schub
 * nach, läge das Abstandsverhältnis Bild für Bild bei ~1 und verließe die Totzone
 * nie — ein langsames Aufziehen zoomte dann überhaupt nicht mehr. Der Zoom-Bezug
 * wird deshalb NUR nachgezogen, wenn wirklich gezoomt wurde.
 */
interface PinchState {
  zoomPair: PointerPair;
  panPair: PointerPair;
}

/** Das gemessene (oder eingespritzte) Rechteck der Fläche in Client-Pixeln. */
interface SurfaceRect {
  left: number;
  width: number;
}

/** Pfeiltaste: ein Viertel der Spanne. Mit Umschalt: die ganze Spanne. */
const KEY_PAN_FRACTION = 0.25;
const KEY_PAN_FRACTION_SHIFT = 1;

/** Tastatur- und Doppeltipp-Zoom: Faktor 2, verankert in der Bildmitte. */
const KEY_ZOOM_FACTOR = 2;
const KEY_ZOOM_OUT_FACTOR = 1 / KEY_ZOOM_FACTOR;
const DOUBLE_TAP_ZOOM_FACTOR = KEY_ZOOM_FACTOR;

/** Strg/Cmd + Rad: eine Raste ist ein kleiner Schritt, keine Verdopplung. */
const WHEEL_ZOOM_FACTOR = 1.2;
const WHEEL_ZOOM_OUT_FACTOR = 1 / WHEEL_ZOOM_FACTOR;

/** Anker der Tastatur-Befehle: die Bildmitte (0 = links, 1 = rechts). */
const CENTER_ANCHOR = 0.5;

/**
 * Ein Schub, der aus JEDER Lage bis an den Anschlag reicht — für `Pos1` (ältester
 * Verlauf) und `Ende` (Live-Rand). Der weiteste denkbare Weg ist die ganze
 * Aufbewahrung bei feinster Spanne, also `MAX_SPAN_MS / MIN_SPAN_MS` Spannen weit;
 * `clampViewport` hält am Anschlag an, ohne die Spanne zu stauchen. So braucht
 * diese Fläche keine eigene Rechnung über Zeitpunkte — nur die beiden Grenzen, die
 * ohnehin in viewport.ts stehen.
 */
const EDGE_SWEEP_FRACTION = MAX_SPAN_MS / MIN_SPAN_MS;

/**
 * Trefferfläche und Zuständigkeit für die Achsen — bewusst als Klassen und NICHT
 * als `style`:
 *   `touch-pan-y` gibt allein die Waagerechte ab, die Senkrechte bleibt Seitenlauf
 *      (`touch-action: none` wäre der naheliegende Griff und der Fehler: bei vier
 *      gestapelten Panels wäre die Seite dort nicht mehr scrollbar);
 *   `min-h-[180px]` hält die Fläche greifbar — das SVG hängt an `h-auto w-full` auf
 *      viewBox 720 × 220 und wäre auf einem kleinen Schirm rund 85 px hoch; ein
 *      Zwei-Finger-Griff mit Arbeitshandschuh ist auf einem 85-px-Streifen keine
 *      Geste mehr.
 * Als Inline-Stil wäre ausgerechnet `touch-action` unprüfbar: jsdom verwirft
 * Eigenschaften, die seine CSS-Umsetzung nicht kennt, still aus dem style-Attribut.
 */
const SURFACE_CLASS =
  "relative touch-pan-y min-h-[180px] rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

/**
 * Die Fläche rechnet OHNE Ränder: Anteile beziehen sich auf ihre volle Breite. Die
 * Polsterung des Diagramms (PAD) lebt in viewBox-Einheiten INNERHALB des Diagramms;
 * sie hier umzurechnen hieße, dieselbe Zahl ein zweites Mal zu führen und mit dem
 * Streckfaktor des SVG zu multiplizieren — beides gehört nicht in diese Datei.
 * Preis, ausdrücklich: Anker und Schub weichen um den Polster-Anteil ab (rund 9 %
 * der Breite). Das verschiebt die Geste leicht, es verfälscht keine Messwerte.
 */
const NO_PAD_PX = 0;

/** jsdom kennt die Zeiger-Fang-API nicht — ohne diese Frage wirft jeder Test. */
function capturePointer(element: HTMLElement, pointerId: number): void {
  if (typeof element.setPointerCapture === "function") {
    element.setPointerCapture(pointerId);
  }
}

/** Gegenstück zu `capturePointer`, mit derselben Frage vor jedem Aufruf. */
function releasePointer(element: HTMLElement, pointerId: number): void {
  if (
    typeof element.hasPointerCapture !== "function" ||
    typeof element.releasePointerCapture !== "function"
  ) {
    return;
  }
  if (element.hasPointerCapture(pointerId)) {
    element.releasePointerCapture(pointerId);
  }
}

export function TrendViewportSurface({
  viewport,
  nowMs,
  onPan,
  onZoom,
  onGestureEnd,
  surfaceWidthPx,
  children,
}: TrendViewportSurfaceProps) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  /** Aktuelle Stelle jedes liegenden Zeigers. Leer heißt: keine Geste läuft. */
  const pointersRef = useRef(new Map<number, PointerPosition>());
  const dragRef = useRef<DragState | null>(null);
  const pinchRef = useRef<PinchState | null>(null);
  /** Die letzte Berührung, die NICHT geschoben hat — Bezug für den Doppeltipp. */
  const lastTapRef = useRef<{ ms: number; x: number } | null>(null);

  const readSurface = useCallback((): SurfaceRect => {
    const rect = surfaceRef.current?.getBoundingClientRect();
    // Die Einspritzung gewinnt über die Messung: in jsdom ist die gemessene Breite
    // immer 0, und eine Geste ohne Breite bewegt nichts (der Null-Schutz in
    // gesture.ts liefert 0 statt NaN — ein NaN in der Achsen-Domäne bliebe still).
    return { left: rect?.left ?? 0, width: surfaceWidthPx ?? rect?.width ?? 0 };
  }, [surfaceWidthPx]);

  /** Die beiden ältesten liegenden Zeiger als Paar — stabil nach Kennung sortiert. */
  const readPair = (): PointerPair | null => {
    const positions = [...pointersRef.current.entries()]
      .sort((left, right) => left[0] - right[0])
      .map(([, position]) => position);
    const first = positions[0];
    const second = positions[1];
    if (first === undefined || second === undefined) {
      return null;
    }
    return [first, second];
  };

  const reportPinch = (rect: SurfaceRect): void => {
    const state = pinchRef.current;
    const pair = readPair();
    if (state === null || pair === null) {
      return;
    }

    // ERST zoomen, verankert am START-Mittelpunkt des Bezugspaars, DANN schieben:
    // die Wanderung des Mittelpunkts steckt bereits im Schub. Am aktuellen
    // Mittelpunkt verankert oder in umgekehrter Reihenfolge liefe der Inhalt unter
    // den Fingern doppelt so weit wie die Hand.
    const zoom = pinchIntents(state.zoomPair, pair, rect.left, rect.width, NO_PAD_PX, NO_PAD_PX);
    if (zoom.factor !== 1) {
      onZoom(zoom.factor, zoom.anchorFraction);
      state.zoomPair = pair;
    }

    const shove = pinchIntents(state.panPair, pair, rect.left, rect.width, NO_PAD_PX, NO_PAD_PX);
    if (shove.panFraction !== 0) {
      onPan(-shove.panFraction);
      state.panPair = pair;
    }
  };

  const reportDrag = (event: ReactPointerEvent<HTMLDivElement>, rect: SurfaceRect): void => {
    const drag = dragRef.current;
    if (drag === null || drag.pointerId !== event.pointerId) {
      return;
    }
    if (!drag.panning) {
      // Vor der Absichtsschwelle wird NICHT gefangen: der Browser entscheidet erst
      // nach den ersten Pixeln, ob er senkrecht scrollt, und bis dahin liegen die
      // Ereignisse hier. Ein Streifer beim Seiten-Scrollen darf nichts auslösen.
      if (!isHorizontalIntent(event.clientX - drag.startX, event.clientY - drag.startY)) {
        return;
      }
      drag.panning = true;
      const element = surfaceRef.current;
      if (element !== null) {
        capturePointer(element, event.pointerId);
      }
    }
    const fraction = panFraction(event.clientX - drag.lastX, rect.width);
    drag.lastX = event.clientX;
    if (fraction !== 0) {
      onPan(-fraction);
    }
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>): void => {
    const pointers = pointersRef.current;
    const wasIdle = pointers.size === 0;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });

    if (wasIdle) {
      const tap = lastTapRef.current;
      if (tap !== null && isDoubleTap(tap.ms, event.timeStamp, tap.x, event.clientX)) {
        const rect = readSurface();
        lastTapRef.current = null;
        onZoom(
          DOUBLE_TAP_ZOOM_FACTOR,
          anchorRatio(event.clientX, rect.left, rect.width, NO_PAD_PX, NO_PAD_PX),
        );
      }
      dragRef.current = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        lastX: event.clientX,
        panning: false,
      };
      return;
    }

    // Ab dem zweiten Finger ist es ein Griff und kein Zug mehr.
    const pair = readPair();
    if (pair !== null) {
      dragRef.current = null;
      pinchRef.current = { zoomPair: pair, panPair: pair };
    }
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>): void => {
    const pointers = pointersRef.current;
    // Ein Zeiger, der nicht in der Buchführung steht, gehört zu keiner laufenden
    // Geste: nach pointercancel/pointerup/pointerleave bewegt er nichts mehr.
    if (!pointers.has(event.pointerId)) {
      return;
    }
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });

    const rect = readSurface();
    if (pointers.size >= 2) {
      reportPinch(rect);
      return;
    }
    reportDrag(event, rect);
  };

  /**
   * Ende eines Zeigers. `keepTap` ist nur beim regulären Loslassen wahr: ein
   * abgebrochener oder hinausgezogener Zeiger ist keine Berührung, die zu einem
   * Doppeltipp zählen darf.
   */
  const finishPointer = (event: ReactPointerEvent<HTMLDivElement>, keepTap: boolean): void => {
    const pointers = pointersRef.current;
    if (!pointers.delete(event.pointerId)) {
      return;
    }
    const element = surfaceRef.current;
    if (element !== null) {
      releasePointer(element, event.pointerId);
    }

    const drag = dragRef.current;
    if (drag !== null && drag.pointerId === event.pointerId) {
      lastTapRef.current =
        keepTap && !drag.panning ? { ms: event.timeStamp, x: event.clientX } : null;
      dragRef.current = null;
    }
    if (pointers.size < 2) {
      pinchRef.current = null;
    }
    if (pointers.size === 0) {
      onGestureEnd();
    }
  };

  /**
   * Tastatur-Beschleuniger. Was hier nicht behandelt wird, verlässt den Schalter
   * über `default: return` — und zwar VOR jeder Meldung: `Bild-auf`, `Bild-ab`,
   * `Leertaste` und `Escape` sind Seitenlauf bzw. gehören einem umschließenden
   * Dialog. Es fällt hier auch kein `preventDefault()`: die Fläche bricht
   * ausschließlich den Zwei-Finger-touchmove und das Strg/Cmd-Rad ab.
   */
  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>): void => {
    const step = event.shiftKey ? KEY_PAN_FRACTION_SHIFT : KEY_PAN_FRACTION;
    switch (event.key) {
      case "ArrowLeft":
        onPan(-step);
        break;
      case "ArrowRight":
        onPan(step);
        break;
      case "+":
        onZoom(KEY_ZOOM_FACTOR, CENTER_ANCHOR);
        break;
      case "-":
        onZoom(KEY_ZOOM_OUT_FACTOR, CENTER_ANCHOR);
        break;
      case "Home":
        onPan(-EDGE_SWEEP_FRACTION);
        break;
      case "End":
        onPan(EDGE_SWEEP_FRACTION);
        break;
      default:
        return;
    }
    onGestureEnd();
  };

  useEffect(() => {
    const element = surfaceRef.current;
    if (element === null) {
      return;
    }

    // React hängt `touchmove` und `wheel` PASSIV an den Wurzelknoten — ein passiver
    // Zuhörer kann nicht abbrechen. Beide werden deshalb von Hand registriert, am
    // Element selbst (kein Zuhörer am document, kein globaler Eingriff).
    const handleTouchMove = (event: TouchEvent): void => {
      // Genau hier und nirgends sonst im Touch-Pfad: der Ein-Finger-Fall bleibt
      // vollständig beim Browser, sonst wäre die Seite unter vier gestapelten
      // Panels nicht mehr scrollbar.
      if (event.touches.length === 2) {
        event.preventDefault();
      }
    };

    const handleWheel = (event: WheelEvent): void => {
      // Blankes Rad scrollt die Seite — nur Strg/Cmd zoomt.
      if (!event.ctrlKey && !event.metaKey) {
        return;
      }
      if (event.deltaY === 0) {
        return;
      }
      event.preventDefault();
      const rect = readSurface();
      const factor = event.deltaY < 0 ? WHEEL_ZOOM_FACTOR : WHEEL_ZOOM_OUT_FACTOR;
      onZoom(factor, anchorRatio(event.clientX, rect.left, rect.width, NO_PAD_PX, NO_PAD_PX));
      onGestureEnd();
    };

    element.addEventListener("touchmove", handleTouchMove, { passive: false });
    element.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      element.removeEventListener("touchmove", handleTouchMove);
      element.removeEventListener("wheel", handleWheel);
    };
  }, [onGestureEnd, onZoom, readSurface]);

  return (
    <div
      ref={surfaceRef}
      data-testid="trend-viewport-surface"
      role="group"
      tabIndex={0}
      aria-label={`Zeitachse — ${describeViewport(viewport, nowMs)}. Pfeiltasten schieben, Plus und Minus zoomen, Ende springt an den Live-Rand.`}
      className={SURFACE_CLASS}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={(event) => finishPointer(event, true)}
      onPointerCancel={(event) => finishPointer(event, false)}
      onPointerLeave={(event) => finishPointer(event, false)}
      onKeyDown={handleKeyDown}
    >
      {children}
    </div>
  );
}
