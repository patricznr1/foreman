// ============================================================
//  FOREMAN Frontend — lib/machine/use-time-viewport.ts
//  Zweck: Die React-Bindung über den reinen Ausschnitts-Funktionen aus
//         `viewport.ts` — der EINE Zustand, den die Detailsicht über alle
//         gestapelten Panels teilt. Sie hält drei Dinge: den Ausschnitt, die
//         abzurufenden `hours` (monoton) und die Ansage für die Vorlesehilfe.
//         Gerechnet wird hier nichts; jeder Befehl reicht durch `panViewport`,
//         `zoomViewport`, `clampViewport` oder `presetViewport`.
//         KEIN Timer, kein Debounce, kein Intervall: `hours` folgt der
//         Stufenleiter (Gleichheit von Zahlen statt Entprellung), die Ansage
//         hängt an einem Ereignis (Gestenende, Knopfdruck) statt an einer Uhr.
//         Der Ausschnitt wird hier ABSICHTLICH nicht nach `{startMs, endMs}`
//         aufgelöst — das macht das Panel bei jedem Bild. Nur so wächst der
//         Live-Rand bei einem WS-Push weiter, ohne dass diese Sicht tickt.
//  Architektur-Einordnung: View-State-Hook (Schicht 2), gegen die reinen
//         Funktionen aus viewport.ts verdrahtet.
// ============================================================
"use client";

import { useCallback, useState } from "react";

import { DEFAULT_TIME_WINDOW } from "./time-window";
import {
  clampViewport,
  describeViewport,
  isAtFloor,
  isAtWall,
  presetViewport,
  panViewport,
  requiredHours,
  resolveViewport,
  retentionFromMs,
  zoomViewport,
} from "./viewport";

import type { TimeWindowId } from "./time-window";
import type { TrendViewport } from "./viewport";

export interface UseTimeViewportArgs {
  /** Injizierbar für deterministische Tests; sonst der aktuelle Zeitpunkt. */
  nowMs?: number;
}

export interface UseTimeViewportResult {
  /** Der geteilte Ausschnitt — jedes Panel zeichnet denselben. */
  readonly viewport: TrendViewport;
  /** Abzurufende Stunden für die Trend-Route (Vertrag 1–168). */
  readonly hours: number;
  /** Am Zoom-Boden: der Hineinzoomen-Knopf spiegelt das als `disabled`. */
  readonly atFloor: boolean;
  /** An der 7-Tage-Wand: der Älter-Knopf spiegelt das als `disabled`. */
  readonly atWall: boolean;
  /** Läuft der Ausschnitt dem Live-Rand nach? (Abgeleitet, kein Feld.) */
  readonly following: boolean;
  /** Der Ausschnitt in einem Satz — für die sichtbare Statuszeile. */
  readonly description: string;
  /** Text der Live-Region. Leer, solange niemand etwas bedient hat. */
  readonly announcement: string;
  /**
   * Schieben um einen Anteil der Spanne — auf der ZEITACHSE: positiv = Richtung
   * Live-Rand (neuer), negativ = in die Vergangenheit. Ein Zeigerweg nach rechts
   * zieht den Ausschnitt in die Vergangenheit; das Vorzeichen aus `gesture.ts`
   * kommt deshalb umgedreht herein. Umgedreht wird es an der Nahtstelle zum
   * Zeiger, nicht hier — sonst liefe der Knopf `Neuer` rückwärts.
   */
  pan: (fraction: number) => void;
  /** Zoomen (Faktor > 1 = hinein) mit festgehaltenem Ankeranteil (0–1). */
  zoom: (factor: number, anchorFraction: number) => void;
  /** Schnellwahl: Ausschnitt am Live-Rand, Ladefenster zurückgesetzt. */
  quickPick: (id: TimeWindowId) => void;
  /** Zurück an den Live-Rand, Spanne bleibt. */
  toNow: () => void;
  /** An den ältesten über diese Ansicht abrufbaren Verlauf, Spanne bleibt. */
  toOldest: () => void;
  /** Ende einer zusammenhängenden Geste — hier und nur hier spricht die Ansage. */
  endGesture: () => void;
}

interface ViewportState {
  readonly viewport: TrendViewport;
  readonly hours: number;
  readonly announcement: string;
}

/**
 * Ausschnittswechsel während einer Geste: `hours` zieht MONOTON nach.
 * `requiredHours` bekommt den zuletzt geholten Wert als Untergrenze — ohne ihn
 * gäbe jedes Hineinzoomen ein kleineres Ladefenster an, und der bereits geholte
 * Rand fiele wieder heraus, obwohl er schon auf dem Schirm steht.
 * Die Ansage bleibt unberührt: eine Live-Region, die bildweise feuert, ist für
 * Screenreader schlimmer als keine.
 */
function tracked(previous: ViewportState, viewport: TrendViewport, nowMs: number): ViewportState {
  return {
    ...previous,
    viewport,
    hours: requiredHours(viewport, nowMs, previous.hours),
  };
}

/**
 * Knopf-Befehl: Ausschnitt setzen und die Ansage erneuern.
 * `previousHours` entscheidet über die Monotonie — Schnellwahl und `Jetzt`
 * geben 0 und setzen das Ladefenster damit zurück, sonst bliebe man den Rest
 * der Sitzung auf der höchsten einmal erreichten Sprosse.
 */
function commanded(viewport: TrendViewport, nowMs: number, previousHours: number): ViewportState {
  return {
    viewport,
    hours: requiredHours(viewport, nowMs, previousHours),
    announcement: describeViewport(viewport, nowMs),
  };
}

function initialState(nowMs: number): ViewportState {
  const viewport = presetViewport(DEFAULT_TIME_WINDOW);
  return {
    viewport,
    hours: requiredHours(viewport, nowMs, 0),
    // Leer, nicht beschrieben: die Live-Region meldet das ERGEBNIS einer
    // Bedienung. Ein Text beim ersten Bild spräche unaufgefordert.
    announcement: "",
  };
}

/**
 * Der geteilte Ausschnitts-Zustand der Sensor-Detailsicht. Er ersetzt die
 * frühere Fenster-Wahl vollständig — es steht kein zweiter Zustand daneben:
 * die gedrückte Schnellwahl wird über `matchPreset` aus dem Ausschnitt
 * ZURÜCKGELESEN, und der Folge-Modus ist aus dem rechten Rand abgeleitet.
 */
export function useTimeViewport({ nowMs }: UseTimeViewportArgs = {}): UseTimeViewportResult {
  const readNow = useCallback(() => nowMs ?? Date.now(), [nowMs]);
  const [state, setState] = useState<ViewportState>(() => initialState(nowMs ?? Date.now()));

  const pan = useCallback(
    (fraction: number) => {
      const now = readNow();
      setState((previous) => tracked(previous, panViewport(previous.viewport, fraction, now), now));
    },
    [readNow],
  );

  const zoom = useCallback(
    (factor: number, anchorFraction: number) => {
      const now = readNow();
      setState((previous) =>
        tracked(previous, zoomViewport(previous.viewport, factor, anchorFraction, now), now),
      );
    },
    [readNow],
  );

  const quickPick = useCallback(
    (id: TimeWindowId) => {
      const now = readNow();
      setState(() => commanded(presetViewport(id), now, 0));
    },
    [readNow],
  );

  const toNow = useCallback(() => {
    const now = readNow();
    setState((previous) => {
      const { startMs, endMs } = resolveViewport(previous.viewport, now);
      const span = endMs - startMs;
      return commanded(clampViewport(now - span, now, now), now, 0);
    });
  }, [readNow]);

  const toOldest = useCallback(() => {
    const now = readNow();
    setState((previous) => {
      const { startMs, endMs } = resolveViewport(previous.viewport, now);
      const span = endMs - startMs;
      const wall = retentionFromMs(now);
      // Das GANZE Fenster wandert an die Wand; nur `startMs` zu setzen würde die
      // Spanne stauchen und das Bild am Anschlag feiner machen, ohne dass jemand
      // gezoomt hat.
      return commanded(clampViewport(wall, wall + span, now), now, previous.hours);
    });
  }, [readNow]);

  const endGesture = useCallback(() => {
    const now = readNow();
    // `previous.viewport` und nicht der Ausschnitt aus dem Renderdurchlauf: ein
    // Knopf, der im selben Ereignis erst schiebt und dann abschließt, sagt sonst
    // den Ausschnitt VOR seinem eigenen Schub an.
    setState((previous) => ({
      ...previous,
      announcement: describeViewport(previous.viewport, now),
    }));
  }, [readNow]);

  const now = readNow();
  const { viewport, hours, announcement } = state;

  return {
    viewport,
    hours,
    announcement,
    atFloor: isAtFloor(viewport, now),
    atWall: isAtWall(viewport, now),
    following: viewport.mode === "follow",
    description: describeViewport(viewport, now),
    pan,
    zoom,
    quickPick,
    toNow,
    toOldest,
    endGesture,
  };
}
