// ============================================================
//  FOREMAN Frontend — components/machine/trend-viewport-surface.test.tsx
//  Zweck: Sichert die Gestenfläche des Sensortrends — die einzige Datei mit
//         Ereignis-Verdrahtung. Geprüft wird VERHALTEN, nicht CSS: jsdom kann
//         `touch-action: pan-y` nicht ausführen, aber es kann zählen, ob wir
//         abbrechen, und es kann die gemeldeten Absichten gegen viewport.ts
//         nachrechnen. Die Breite kommt über `surfaceWidthPx` herein (Bauform von
//         `viewportHeight` in components/alarms/alarm-list.tsx) — ohne sie misst
//         jsdom 0 und der ganze Gestenpfad wäre ungeprüft.
//         jsdom kennt weder PointerEvent noch setPointerCapture; die Ereignisse
//         werden deshalb von Hand aus MouseEvent gebaut (React liest nur den Typ).
// ============================================================
import { useRef, useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  HOUR_MS,
  MAX_SPAN_MS,
  MIN_SPAN_MS,
  describeViewport,
  panViewport,
  resolveViewport,
  retentionFromMs,
} from "@/lib/machine/viewport";
import type { TrendViewport } from "@/lib/machine/viewport";

import { TrendViewportSurface } from "./trend-viewport-surface";

const NOW = Date.UTC(2026, 8, 2, 12, 0, 0);
const SURFACE_WIDTH = 600;

const FOLLOW: TrendViewport = { mode: "follow", spanMs: 8 * HOUR_MS };
const FROZEN: TrendViewport = {
  mode: "frozen",
  startMs: NOW - 10 * HOUR_MS,
  endMs: NOW - 2 * HOUR_MS,
};

/** jsdom hat kein PointerEvent — React unterscheidet Ereignisse nur am Typ. */
function pointerEvent(type: string, pointerId: number, x: number, y: number): Event {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y });
  Object.defineProperty(event, "pointerId", { value: pointerId });
  return event;
}

/** Ein touchmove mit einer gewählten Fingerzahl — nur `touches.length` wird gelesen. */
function touchMoveEvent(fingers: number): Event {
  const event = new Event("touchmove", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "touches", {
    value: Array.from({ length: fingers }, () => ({ clientX: 0, clientY: 0 })),
  });
  return event;
}

function wheelEvent(x: number, deltaY: number, ctrlKey: boolean): Event {
  const event = new MouseEvent("wheel", { bubbles: true, cancelable: true, clientX: x, ctrlKey });
  Object.defineProperty(event, "deltaY", { value: deltaY });
  return event;
}

interface Harness {
  surface: HTMLElement;
  onPan: ReturnType<typeof vi.fn>;
  onZoom: ReturnType<typeof vi.fn>;
  onGestureEnd: ReturnType<typeof vi.fn>;
}

/**
 * Mehrere Tests stellen zwei Flächen nebeneinander (Zwillinge). Die Fläche wird
 * deshalb im EIGENEN Behälter gesucht und nicht über `screen` — sonst fände der
 * zweite Aufbau beide und der Zwilling wäre nicht mehr aufbaubar.
 */
function setup(viewport: TrendViewport = FOLLOW, surfaceWidthPx?: number): Harness {
  const onPan = vi.fn();
  const onZoom = vi.fn();
  const onGestureEnd = vi.fn();
  const { container } = render(
    <TrendViewportSurface
      viewport={viewport}
      nowMs={NOW}
      onPan={onPan}
      onZoom={onZoom}
      onGestureEnd={onGestureEnd}
      surfaceWidthPx={surfaceWidthPx ?? SURFACE_WIDTH}
    >
      <svg role="img" aria-label="Diagramm" />
    </TrendViewportSurface>,
  );
  const surface = container.querySelector('[data-testid="trend-viewport-surface"]');
  if (!(surface instanceof HTMLElement)) {
    throw new Error("Gestenfläche nicht gerendert");
  }
  return { surface, onPan, onZoom, onGestureEnd };
}

/** Alle gemeldeten Schub-Anteile aufsummiert. */
function totalPan(onPan: ReturnType<typeof vi.fn>): number {
  return onPan.mock.calls.reduce((sum, call) => sum + Number(call[0]), 0);
}

/** Alle gemeldeten Zoom-Faktoren aufmultipliziert. */
function totalZoom(onZoom: ReturnType<typeof vi.fn>): number {
  return onZoom.mock.calls.reduce((product, call) => product * Number(call[0]), 1);
}

/** Beide Finger nacheinander bewegen — ein Ereignis je Zeiger, wie im Browser. */
function movePair(surface: HTMLElement, first: number, second: number): void {
  fireEvent(surface, pointerEvent("pointermove", 1, first, 100));
  fireEvent(surface, pointerEvent("pointermove", 2, second, 100));
}

describe("TrendViewportSurface", () => {
  it("bricht den Zwei-Finger-touchmove ab und den Ein-Finger-touchmove NICHT", () => {
    // BELEGT: Spannung F als Verhalten. Der Ein-Finger-Fall ist der wichtigere —
    // er belegt, dass der senkrechte Seitenlauf baulich unangetastet bleibt.
    // ROT BEI: Bedingung `event.touches.length === 2` entfernt (Ein-Finger bricht ab)
    // oder preventDefault im Zwei-Finger-Zweig gestrichen.
    const { surface } = setup();

    const oneFinger = touchMoveEvent(1);
    fireEvent(surface, oneFinger);
    expect(oneFinger.defaultPrevented).toBe(false);

    const twoFingers = touchMoveEvent(2);
    fireEvent(surface, twoFingers);
    expect(twoFingers.defaultPrevented).toBe(true);
  });

  it("meldet den waagerechten Zug und beim senkrechten Zug desselben Betrags nichts", () => {
    // BELEGT: die Absichtsschwelle end-to-end, möglich nur durch surfaceWidthPx.
    // Der senkrechte Zwilling ist Pflicht: ohne ihn bewiese der erste Fall nur,
    // dass überhaupt etwas ankommt.
    // ROT BEI: Absichtsschwelle entfernt (senkrechter Fall meldet) oder die
    // Einspritzung ignoriert und die in jsdom nullbreite Messung genommen
    // (waagerechter Fall meldet 0 statt 0.2).
    const waagerecht = setup();
    fireEvent(waagerecht.surface, pointerEvent("pointerdown", 1, 300, 100));
    fireEvent(waagerecht.surface, pointerEvent("pointermove", 1, 180, 106));
    expect(waagerecht.onPan).toHaveBeenCalledTimes(1);
    expect(waagerecht.onPan).toHaveBeenCalledWith(0.2);

    const senkrecht = setup();
    fireEvent(senkrecht.surface, pointerEvent("pointerdown", 1, 300, 100));
    fireEvent(senkrecht.surface, pointerEvent("pointermove", 1, 306, 220));
    expect(senkrecht.onPan).not.toHaveBeenCalled();
  });

  it("zieht beim Zug nach links Neueres ins Bild und beim Zug nach rechts Älteres", () => {
    // BELEGT: das VORZEICHEN als Ergebnis statt als Zahl — die gemeldete Absicht
    // wird durch panViewport gedreht und der entstandene Ausschnitt geprüft. Eine
    // Zeigergeste nach rechts zieht den Ausschnitt in die Vergangenheit.
    // ROT BEI: die Umkehr des gesture.ts-Vorzeichens weglassen (`onPan(fraction)`
    // statt `onPan(-fraction)`) — beide Richtungen kippen.
    const links = setup(FROZEN);
    fireEvent(links.surface, pointerEvent("pointerdown", 1, 300, 100));
    fireEvent(links.surface, pointerEvent("pointermove", 1, 180, 100));
    const nachLinks = resolveViewport(
      panViewport(FROZEN, Number(links.onPan.mock.calls[0]?.[0]), NOW),
      NOW,
    );
    expect(nachLinks.endMs).toBeGreaterThan(FROZEN.endMs);
    expect(nachLinks.endMs - nachLinks.startMs).toBe(FROZEN.endMs - FROZEN.startMs);

    const rechts = setup(FROZEN);
    fireEvent(rechts.surface, pointerEvent("pointerdown", 1, 300, 100));
    fireEvent(rechts.surface, pointerEvent("pointermove", 1, 420, 100));
    const nachRechts = resolveViewport(
      panViewport(FROZEN, Number(rechts.onPan.mock.calls[0]?.[0]), NOW),
      NOW,
    );
    expect(nachRechts.endMs).toBeLessThan(FROZEN.endMs);
    expect(nachRechts.endMs - nachRechts.startMs).toBe(FROZEN.endMs - FROZEN.startMs);
  });

  it("räumt bei pointercancel die Buchführung — der verwaiste Zeiger bewegt nichts mehr und blockiert nichts", () => {
    // BELEGT: der klassische Weg, wie ein Diagramm bis zum Neuladen tot bleibt —
    // ein Finger verlässt den Bildschirmrand, der Wirt glaubt weiter an eine
    // laufende Geste. Zwei Folgen, beide eingefordert: (1) das verwaiste
    // pointermove meldet nichts; (2) der Zeiger ist WIRKLICH ausgebucht — bliebe er
    // als Phantom stehen, hielte er die Fläche dauerhaft im Zwei-Finger-Zustand:
    // die nächste Ein-Finger-Geste wäre ein Griff statt eines Zuges (Zoom!) und ihr
    // Ende käme nie wieder an. Der Durchlauf ohne Abbruch ist die Aufbau-Kontrolle.
    // ROT BEI: pointercancel-Handler entfernt (erste Zusicherung); die Prüfung
    // `pointers.has(event.pointerId)` im Move-Zweig gestrichen (zweite: der
    // verwaiste Zeiger wird wieder eingebucht, die folgende Geste meldet einen Zoom
    // und ihr Gestenende bleibt aus).
    const { surface, onPan, onZoom, onGestureEnd } = setup();
    fireEvent(surface, pointerEvent("pointerdown", 1, 300, 100));
    fireEvent(surface, pointerEvent("pointermove", 1, 240, 100));
    fireEvent(surface, pointerEvent("pointercancel", 1, 240, 100));
    fireEvent(surface, pointerEvent("pointermove", 1, 120, 100));
    expect(onPan).toHaveBeenCalledTimes(1);
    expect(onGestureEnd).toHaveBeenCalledTimes(1);

    fireEvent(surface, pointerEvent("pointerdown", 2, 300, 100));
    fireEvent(surface, pointerEvent("pointermove", 2, 180, 100));
    fireEvent(surface, pointerEvent("pointerup", 2, 180, 100));
    expect(onZoom).not.toHaveBeenCalled();
    expect(onPan).toHaveBeenCalledTimes(2);
    expect(onPan).toHaveBeenLastCalledWith(0.2);
    expect(onGestureEnd).toHaveBeenCalledTimes(2);

    const durchgehend = setup();
    fireEvent(durchgehend.surface, pointerEvent("pointerdown", 1, 300, 100));
    fireEvent(durchgehend.surface, pointerEvent("pointermove", 1, 240, 100));
    fireEvent(durchgehend.surface, pointerEvent("pointermove", 1, 120, 100));
    expect(durchgehend.onPan).toHaveBeenCalledTimes(2);
  });

  it("fängt den Zeiger, wenn die Umgebung es kann — und läuft ohne die API weiter", () => {
    // BELEGT: die Zusicherung im Quelltext, dass der fehlende Zeiger-Fang in jsdom
    // NICHT wirft. Der erste Fall ist der Kontroll-Zwilling: ist die Methode da,
    // wird sie auch wirklich mit der Zeiger-Kennung gerufen.
    // ROT BEI: Existenz-Check entfernt (zweiter Fall wirft) oder capturePointer
    // gar nicht gerufen (erster Fall meldet keinen Aufruf).
    const vorhanden = setup();
    const setPointerCapture = vi.fn();
    Object.defineProperty(vorhanden.surface, "setPointerCapture", { value: setPointerCapture });
    fireEvent(vorhanden.surface, pointerEvent("pointerdown", 7, 300, 100));
    fireEvent(vorhanden.surface, pointerEvent("pointermove", 7, 180, 100));
    expect(setPointerCapture).toHaveBeenCalledWith(7);

    const fehlend = setup();
    expect(fehlend.surface).not.toHaveProperty("setPointerCapture");
    fireEvent(fehlend.surface, pointerEvent("pointerdown", 7, 300, 100));
    fireEvent(fehlend.surface, pointerEvent("pointermove", 7, 180, 100));
    expect(fehlend.onPan).toHaveBeenCalledTimes(1);
  });

  it("meldet den Zwei-Finger-Griff in SCHRITTEN, nicht als Gesamtstrecke", () => {
    // BELEGT: die Entscheidung im Quelltext (Bezugspaare werden nach jeder Meldung
    // nachgezogen). Der Fingerabstand verdoppelt sich einmal — das Produkt aller
    // gemeldeten Faktoren muss deshalb genau 2 sein, nicht 3. Und weil der
    // Mittelpunkt am Ende wieder dort liegt, wo er begann, muss sich der Schub zu
    // 0 aufheben.
    // ROT BEI: `state.zoomPair = pair` bzw. `state.panPair = pair` entfernt — dann
    // meldet jedes Ereignis die Strecke seit Gestenbeginn, das Produkt wird 3 und
    // die Schub-Summe verschiebt sich.
    const { surface, onZoom, onPan } = setup();
    fireEvent(surface, pointerEvent("pointerdown", 1, 250, 100));
    fireEvent(surface, pointerEvent("pointerdown", 2, 350, 100));

    movePair(surface, 200, 400);

    expect(onZoom.mock.calls.length).toBeGreaterThan(1);
    expect(totalZoom(onZoom)).toBeCloseTo(2, 6);
    for (const call of onZoom.mock.calls) {
      expect(Number(call[0])).toBeLessThan(2);
    }
    expect(totalPan(onPan)).toBeCloseTo(0, 6);
  });

  it("verankert den Zoom am START-Mittelpunkt und meldet ihn VOR dem Schub", () => {
    // BELEGT: die Reihenfolge-Zusicherung aus gesture.ts. Der Startmittelpunkt liegt
    // bei 150 px von 600 (Anteil 0.25), der aktuelle nach dem ersten Ereignis bei
    // 125 px (0.2083) — der Test unterscheidet die beiden Anker also wirklich.
    // ROT BEI: mit dem aktuellen Paar verankern (Anteil wird 0.2083) oder den Schub
    // vor dem Zoom melden (die Aufruf-Reihenfolge kippt).
    const { surface, onZoom, onPan } = setup();
    fireEvent(surface, pointerEvent("pointerdown", 1, 100, 100));
    fireEvent(surface, pointerEvent("pointerdown", 2, 200, 100));

    fireEvent(surface, pointerEvent("pointermove", 1, 50, 100));

    expect(Number(onZoom.mock.calls[0]?.[1])).toBeCloseTo(0.25, 6);
    const ersterZoom = onZoom.mock.invocationCallOrder[0];
    const ersterSchub = onPan.mock.invocationCallOrder[0];
    expect(ersterZoom).toBeDefined();
    expect(ersterSchub).toBeDefined();
    expect(Number(ersterZoom)).toBeLessThan(Number(ersterSchub));
  });

  it("schiebt, wenn zwei Finger sich gemeinsam bewegen, ohne dabei zu zoomen", () => {
    // BELEGT: die WEICHE WAND an ihrer Wurzel — zwei aufgelegte Knöchel, die
    // seitlich wandern, sind ein Schub und kein Zoom. Deshalb bleibt die Geste am
    // Zoom-Boden lebendig, statt tot zu wirken. Beide Finger wandern um 6 px nach
    // rechts, der Abstand bleibt in der Totzone.
    // ROT BEI: die Mittelpunkt-Verschiebung aus dem Pinch-Zweig streichen (kein
    // Schub) oder die Totzone ignorieren (es entsteht ein Zoom).
    const { surface, onZoom, onPan } = setup();
    fireEvent(surface, pointerEvent("pointerdown", 1, 250, 100));
    fireEvent(surface, pointerEvent("pointerdown", 2, 350, 100));

    movePair(surface, 256, 356);

    expect(onZoom).not.toHaveBeenCalled();
    expect(totalPan(onPan)).toBeCloseTo(-0.01, 6);
  });

  it("zoomt beim Doppeltipp auf die Tippstelle — ein einzelner Tipp zoomt nicht", () => {
    // BELEGT: der Doppeltipp als Zoom-Beschleuniger, samt seiner Verankerung an der
    // getippten Stelle (150 px von 600 = 0.25). Der Einzeltipp ist die
    // Aufbau-Kontrolle: ohne ihn bewiese der erste Fall nur, dass irgendeine
    // Berührung zoomt.
    // ROT BEI: den Doppeltipp-Zweig entfernen (erster Fall) oder bei JEDEM
    // pointerdown zoomen (zweiter Fall).
    const doppelt = setup();
    fireEvent(doppelt.surface, pointerEvent("pointerdown", 1, 150, 100));
    fireEvent(doppelt.surface, pointerEvent("pointerup", 1, 150, 100));
    fireEvent(doppelt.surface, pointerEvent("pointerdown", 2, 150, 100));
    expect(doppelt.onZoom).toHaveBeenCalledTimes(1);
    expect(Number(doppelt.onZoom.mock.calls[0]?.[0])).toBeGreaterThan(1);
    expect(Number(doppelt.onZoom.mock.calls[0]?.[1])).toBeCloseTo(0.25, 6);

    const einzeln = setup();
    fireEvent(einzeln.surface, pointerEvent("pointerdown", 1, 150, 100));
    fireEvent(einzeln.surface, pointerEvent("pointerup", 1, 150, 100));
    expect(einzeln.onZoom).not.toHaveBeenCalled();
  });

  it("zoomt beim Strg-Rad und überlässt das blanke Rad der Seite", () => {
    // BELEGT: der zweite und letzte Ort, an dem preventDefault fällt. Ein blankes
    // Mausrad scrollt die Seite — es darf weder abbrechen noch zoomen.
    // ROT BEI: die Strg/Cmd-Prüfung entfernen (blankes Rad zoomt und bricht ab)
    // oder preventDefault im Strg-Zweig streichen.
    const { surface, onZoom } = setup();

    const blank = wheelEvent(150, -100, false);
    fireEvent(surface, blank);
    expect(blank.defaultPrevented).toBe(false);
    expect(onZoom).not.toHaveBeenCalled();

    const mitStrg = wheelEvent(150, -100, true);
    fireEvent(surface, mitStrg);
    expect(mitStrg.defaultPrevented).toBe(true);
    expect(onZoom).toHaveBeenCalledTimes(1);
    expect(Number(onZoom.mock.calls[0]?.[0])).toBeGreaterThan(1);
    expect(Number(onZoom.mock.calls[0]?.[1])).toBeCloseTo(0.25, 6);
  });

  it("ist fokussierbar, schiebt mit den Pfeiltasten und springt mit Ende an den Live-Rand", () => {
    // BELEGT: Spannung E ohne Layout. Geprüft wird das ERGEBNIS der gemeldeten
    // Absicht durch panViewport, nicht bloß der Aufruf: ArrowLeft schiebt um ein
    // Viertel der Spanne in die Vergangenheit, Umschalt um die ganze Spanne, Ende
    // bringt den festen Ausschnitt zurück ins Mitlaufen, Pos1 an die 7-Tage-Wand.
    // ROT BEI: tabIndex auf das <svg> verlegen (Fokus-Zusicherung trifft das falsche
    // Element); ArrowLeft/ArrowRight vertauschen; den Umschalt-Zweig entfernen;
    // Ende/Pos1 mit einem zu kleinen Bruchteil melden (Anschlag wird nicht erreicht).
    const { surface, onPan } = setup(FROZEN);
    surface.focus();
    expect(document.activeElement).toBe(surface);

    fireEvent.keyDown(surface, { key: "ArrowLeft" });
    const nachLinks = resolveViewport(
      panViewport(FROZEN, Number(onPan.mock.calls[0]?.[0]), NOW),
      NOW,
    );
    expect(nachLinks.startMs).toBe(FROZEN.startMs - 2 * HOUR_MS);
    expect(nachLinks.endMs - nachLinks.startMs).toBe(FROZEN.endMs - FROZEN.startMs);

    fireEvent.keyDown(surface, { key: "ArrowLeft", shiftKey: true });
    const ganzeSpanne = resolveViewport(
      panViewport(FROZEN, Number(onPan.mock.calls[1]?.[0]), NOW),
      NOW,
    );
    expect(ganzeSpanne.startMs).toBe(FROZEN.startMs - 8 * HOUR_MS);

    fireEvent.keyDown(surface, { key: "End" });
    expect(panViewport(FROZEN, Number(onPan.mock.calls[2]?.[0]), NOW).mode).toBe("follow");

    fireEvent.keyDown(surface, { key: "Home" });
    const anDerWand = resolveViewport(
      panViewport(FROZEN, Number(onPan.mock.calls[3]?.[0]), NOW),
      NOW,
    );
    expect(anDerWand.startMs).toBe(retentionFromMs(NOW));
    expect(anDerWand.endMs - anDerWand.startMs).toBe(FROZEN.endMs - FROZEN.startMs);
  });

  it("zoomt mit Plus und Minus um die Bildmitte", () => {
    // BELEGT: der Tastatur-Zoom ist derselbe Faktor 2 wie der Plus-Knopf und
    // verankert mittig — sonst wanderte das Bild bei jedem Tastendruck seitlich.
    // ROT BEI: Plus und Minus vertauschen oder den Anker aus der Mitte nehmen.
    const { surface, onZoom } = setup();
    fireEvent.keyDown(surface, { key: "+" });
    fireEvent.keyDown(surface, { key: "-" });
    expect(onZoom.mock.calls[0]).toEqual([2, 0.5]);
    expect(onZoom.mock.calls[1]).toEqual([0.5, 0.5]);
  });

  it("fängt Bild-auf, Bild-ab, Leertaste und Escape NICHT ab", () => {
    // BELEGT: der Schutz dessen, der keinen anderen Weg durch die Seite hat. Bild-
    // auf/ab sind Seitenlauf, Escape gehört einem umschließenden Dialog. Geprüft
    // werden BEIDE Hälften: kein defaultPrevented UND keine gemeldete Absicht.
    // ROT BEI: Bild-auf/ab an das Ganz-Spannen-Schieben binden oder ein
    // preventDefault() in den Tasten-Zweig setzen.
    const { surface, onPan, onZoom, onGestureEnd } = setup();
    for (const key of ["PageUp", "PageDown", " ", "Escape"]) {
      const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
      fireEvent(surface, event);
      expect(event.defaultPrevented).toBe(false);
    }
    expect(onPan).not.toHaveBeenCalled();
    expect(onZoom).not.toHaveBeenCalled();
    expect(onGestureEnd).not.toHaveBeenCalled();
  });

  it("meldet das Gestenende genau einmal je Geste, nicht je Bild", () => {
    // BELEGT: eine aria-live-Zeile, die bildweise feuert, ist für Screenreader
    // schlimmer als gar keine Ansage — und in einer sehenden Durchsicht fällt das
    // niemandem auf. Zehn Zeigerbewegungen, genau EIN Textwechsel. Der Zählvergleich
    // ist hier zulässig, weil die Zahl selbst die Zusicherung ist.
    // ROT BEI: onGestureEnd aus dem Move-Zweig heraus rufen (zehn Wechsel).
    render(<AnnouncingHarness />);
    const surface = screen.getByTestId("trend-viewport-surface");
    const ansage = screen.getByTestId("ansage");

    const texte: string[] = [ansage.textContent ?? ""];
    fireEvent(surface, pointerEvent("pointerdown", 1, 500, 100));
    for (let step = 1; step <= 10; step += 1) {
      fireEvent(surface, pointerEvent("pointermove", 1, 500 - step * 20, 100));
      texte.push(ansage.textContent ?? "");
    }
    expect(texte.every((text) => text === "")).toBe(true);

    fireEvent(surface, pointerEvent("pointerup", 1, 300, 100));
    texte.push(ansage.textContent ?? "");

    const wechsel = texte.filter((text, index) => index > 0 && text !== texte[index - 1]);
    expect(wechsel).toHaveLength(1);
    expect(ansage).toHaveTextContent(describeViewport(FOLLOW, NOW));
  });

  it("bewegt ohne messbare Breite nichts, statt NaN zu melden", () => {
    // BELEGT: der jsdom- und Layout-Fehlerfall. Ohne Einspritzung misst
    // getBoundingClientRect 0; eine Geste darf dann nichts bewegen — aber niemals
    // NaN in die Achsen-Domäne schreiben, denn ein NaN dort lässt das SVG STILL
    // leer, ohne Fehler und ohne Log-Zeile.
    // ROT BEI: den Null-Schutz in gesture.ts umgehen und selbst durch die Breite
    // teilen (die Meldung wird NaN statt auszubleiben).
    const { surface, onPan } = setup(FOLLOW, 0);
    fireEvent(surface, pointerEvent("pointerdown", 1, 300, 100));
    fireEvent(surface, pointerEvent("pointermove", 1, 180, 100));
    expect(onPan).not.toHaveBeenCalled();
  });

  it("trägt Ausschnitt und Bedienung im aria-label der umschließenden Gruppe", () => {
    // BELEGT: der Fokusträger ist die Gruppe und nicht das <svg role='img'> — die
    // img-Rolle trägt keine interaktive Semantik, ihre Bedienbarkeit würde nicht
    // angekündigt. Der Ausschnitt steht als EIN Satz aus describeViewport darin,
    // nicht als zweite, eigene Formulierung.
    // ROT BEI: role/aria-label auf das <svg> verlegen oder den Ausschnitt im Label
    // von Hand formulieren statt aus describeViewport zu nehmen.
    const { surface } = setup();
    expect(surface).toHaveAttribute("role", "group");
    expect(surface.getAttribute("aria-label")).toContain(describeViewport(FOLLOW, NOW));
    expect(surface.getAttribute("aria-label")).toContain("Pfeiltasten");
  });

  it("gibt die Waagerechte ab und behält die Senkrechte der Seite", () => {
    // BELEGT: `touch-action: pan-y` steht wirklich auf der Fläche und die
    // Trefferfläche hat eine Mindesthöhe (auf einem Telefon wäre das Diagramm sonst
    // rund 85 px hoch — kein Griff mehr für eine behandschuhte Hand).
    // NICHT BELEGT (Grenze): dass die Seite darunter wirklich weiterscrollt. jsdom
    // führt touch-action nicht aus, es sieht nur die Deklaration — und aus einem
    // style-Attribut sähe es sie nicht einmal dort, weil es unbekannte
    // Eigenschaften still verwirft. Deshalb stehen beide als Klasse.
    // ROT BEI: `touch-action: none` setzen (Klasse `touch-none`) oder die
    // Mindesthöhe entfernen.
    const { surface } = setup();
    expect(surface).toHaveClass("touch-pan-y");
    expect(surface).toHaveClass("min-h-[180px]");
  });

  it("reicht mit Pos1 und Ende garantiert bis an beide Anschläge — auch bei feinster Spanne", () => {
    // BELEGT: der Bruchteil für Pos1/Ende ist aus MAX_SPAN_MS/MIN_SPAN_MS abgeleitet
    // und nicht geschätzt. Geprüft im ungünstigsten Fall: feinste Spanne, Ausschnitt
    // dicht am Live-Rand — von dort ist der Weg zur Wand am weitesten.
    // ROT BEI: den Bruchteil auf einen festen kleinen Wert setzen (etwa 10) — der
    // Anschlag wird dann nicht erreicht.
    const feinstUndNeu: TrendViewport = {
      mode: "frozen",
      startMs: NOW - MIN_SPAN_MS - HOUR_MS,
      endMs: NOW - HOUR_MS,
    };
    const { surface, onPan } = setup(feinstUndNeu);

    fireEvent.keyDown(surface, { key: "Home" });
    const anDerWand = resolveViewport(
      panViewport(feinstUndNeu, Number(onPan.mock.calls[0]?.[0]), NOW),
      NOW,
    );
    expect(anDerWand.startMs).toBe(NOW - MAX_SPAN_MS);
    expect(anDerWand.endMs - anDerWand.startMs).toBe(MIN_SPAN_MS);
  });
});

/**
 * Prüfstand für die Ansage: EINE Live-Region, die ihren Text ausschließlich im
 * Gestenende bezieht — genau so, wie `useTimeViewport` sie später speist. Der
 * Zähler im Text macht jeden Wechsel sichtbar; ohne ihn wären zehn gleiche
 * Zuweisungen von einer nicht zu unterscheiden.
 */
function AnnouncingHarness() {
  const [announcement, setAnnouncement] = useState("");
  const countRef = useRef(0);
  return (
    <>
      <p data-testid="ansage" role="status" aria-live="polite">
        {announcement}
      </p>
      <TrendViewportSurface
        viewport={FOLLOW}
        nowMs={NOW}
        onPan={() => {}}
        onZoom={() => {}}
        onGestureEnd={() => {
          countRef.current += 1;
          setAnnouncement(`${describeViewport(FOLLOW, NOW)} (${countRef.current})`);
        }}
        surfaceWidthPx={SURFACE_WIDTH}
      >
        <svg role="img" aria-label="Diagramm" />
      </TrendViewportSurface>
    </>
  );
}
