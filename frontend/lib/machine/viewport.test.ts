// ============================================================
//  FOREMAN Frontend — lib/machine/viewport.test.ts
//  Zweck: Sichert den Ausschnitt des Sensorverlaufs als reine Arithmetik —
//         Klemmung an beiden Anschlägen, den ABGELEITETEN Folge-Modus, den
//         festgehaltenen Zoom-Anker und die Abruf-Stufenleiter. Kein DOM, kein
//         Layout, kein Fake-Timer: jede Zusicherung ist eine Gleichheit von Zahlen.
//         Jeder Test nennt, WAS er belegt und WELCHE Mutation ihn rot machen muss.
// ============================================================
import { describe, expect, it } from "vitest";

import { BUCKET_MS, MAX_BACKEND_HOURS } from "./time-window";
import {
  clampViewport,
  describeSpan,
  describeViewport,
  HOUR_MS,
  isAtWall,
  matchPreset,
  MAX_SPAN_MS,
  MIN_SPAN_MS,
  panViewport,
  presetViewport,
  requiredHours,
  resolveViewport,
  retentionFromMs,
  snapMs,
  zoomViewport,
} from "./viewport";

import type { TrendViewport } from "./viewport";

const NOW = Date.parse("2026-06-17T12:00:00Z");

/** Spanne des aufgelösten Ausschnitts (spart die Union-Verzweigung im Test). */
function spanOf(viewport: TrendViewport, nowMs: number): number {
  const { startMs, endMs } = resolveViewport(viewport, nowMs);
  return endMs - startMs;
}

/** Die Zeit, die im Bild an einem Ankeranteil steht (0 = links, 1 = rechts). */
function timeAt(viewport: TrendViewport, fraction: number, nowMs: number): number {
  const { startMs, endMs } = resolveViewport(viewport, nowMs);
  return startMs + (endMs - startMs) * fraction;
}

/** Deterministischer Zufall (mulberry32) — ohne Seed wäre ein Fehlschlag nicht nachstellbar. */
function makeRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

describe("clampViewport", () => {
  /**
   * BELEGT: Der Kern der Modus-Ableitung als Zahl — ein Ausschnitt, dessen Ende über
   * `jetzt` hinausgeschoben wird, kommt mit UNVERÄNDERTER Spanne und im Folge-Modus
   * zurück. Das Mitlaufen ist kein Feld, das man zu setzen vergessen kann.
   * ROT BEI: In Schritt (b) nur `right = nowMs` setzen, ohne `left` mitzuziehen —
   * die Spanne schrumpft.
   */
  it("schiebt das ganze Fenster, wenn der rechte Rand hinter jetzt liegt — die Spanne bleibt", () => {
    const span = 4 * HOUR_MS;
    const drift = 30 * BUCKET_MS;

    const viewport = clampViewport(NOW - span + drift, NOW + drift, NOW);

    expect(viewport.mode).toBe("follow");
    expect(spanOf(viewport, NOW)).toBe(span);
    expect(resolveViewport(viewport, NOW).endMs).toBe(NOW);
  });

  /**
   * BELEGT: Drei Zusicherungen — bei Abstand GENAU `snapMs` folgt der Ausschnitt, bei
   * `snapMs + 1` steht er fest, und die Fangzone fällt nie unter eine Bucket-Breite.
   * Ohne die zweite Hälfte belegte die erste nur, dass immer „follow" herauskommt.
   * ROT BEI: (1) Folge-Rückfall entfernen → erste Zusicherung; (2) immer „follow"
   * liefern → zweite; (3) in snapMs `Math.max(BUCKET_MS, …)` durch das bloße Produkt
   * ersetzen → dritte (2 % von 20 Minuten sind 24 Sekunden).
   */
  it("kippt an der Fangzone in BEIDE Richtungen, und snapMs fällt nie unter eine Bucket-Breite", () => {
    const span = 8 * HOUR_MS;
    const zone = snapMs(span);

    const onEdge = clampViewport(NOW - zone - span, NOW - zone, NOW);
    expect(onEdge.mode).toBe("follow");

    const beyond = clampViewport(NOW - zone - 1 - span, NOW - zone - 1, NOW);
    expect(beyond.mode).toBe("frozen");
    expect(resolveViewport(beyond, NOW).endMs).toBe(NOW - zone - 1);

    expect(snapMs(MIN_SPAN_MS)).toBe(BUCKET_MS);
  });

  /**
   * BELEGT: Am linken Anschlag hält das Schieben an, ohne die Spanne zu stauchen —
   * nach zehn Schüben steht der linke Rand auf der Wand, die Spanne ist unverändert,
   * und ein elfter Schub ändert nichts mehr (Idempotenz). Eine naive Klemme nur auf
   * `start` machte das Bild am Anschlag stillschweigend feiner, obwohl niemand zoomte.
   * ROT BEI: In Schritt (c) nur `left = wall` setzen statt das Fenster zu schieben —
   * die Spannen-Zusicherung. Die Idempotenz bliebe dabei grün; sie steht deshalb
   * VOR ihr, damit im Fehlerfall sichtbar ist, dass sie allein nichts belegt hätte.
   */
  it("hält vor der 7-Tage-Wand an, ohne die Spanne zu stauchen; zehnmal schieben = einmal schieben", () => {
    const span = 24 * HOUR_MS;
    let viewport = presetViewport("day");
    for (let step = 0; step < 10; step += 1) {
      viewport = panViewport(viewport, -1, NOW);
    }
    const atWall = resolveViewport(viewport, NOW);

    expect(atWall.startMs).toBe(retentionFromMs(NOW));
    expect(isAtWall(viewport, NOW)).toBe(true);

    const onceMore = resolveViewport(panViewport(viewport, -1, NOW), NOW);
    expect(onceMore).toEqual(atWall);

    expect(atWall.endMs - atWall.startMs).toBe(span);
  });
});

describe("zoomViewport", () => {
  /**
   * BELEGT: Die eigentliche Zusicherung jeder Pinch-Geste — „unter dem Finger bleibt
   * derselbe Zeitpunkt" — als reine Arithmetik, an beiden Rändern und in der Mitte.
   * Die Spannen-Zusicherung ist der Aufbau-Zwilling: ohne sie bestünde der Test auch,
   * wenn zoomViewport seine Eingabe unverändert zurückgäbe.
   * ROT BEI: `anchorFraction` in zoomViewport durch die feste Mitte 0.5 ersetzen —
   * die Fälle 0 und 1 werden rot, der Fall 0.5 bleibt grün. Die drei Anker sind
   * deshalb DREI Testfälle und keine Schleife: nur so ist im Fehlerfall sichtbar,
   * dass der Test wirklich den Anker unterscheidet und nicht nur „es ändert sich etwas".
   */
  it.each([0, 0.5, 1])("hält die Zeit unter dem Ankeranteil %s fest", (anchor) => {
    const before = presetViewport("day");
    const after = zoomViewport(before, 2, anchor, NOW);

    expect(spanOf(after, NOW)).toBe(spanOf(before, NOW) / 2);
    expect(Math.abs(timeAt(after, anchor, NOW) - timeAt(before, anchor, NOW))).toBeLessThanOrEqual(
      1,
    );
  });

  /**
   * BELEGT: Der Zoom-Boden ist ein Zahlenwert, kein Zeichenzufall — und die einzige
   * Reihenfolge-Abhängigkeit des Moduls: die Zeit unter dem Anker bleibt auch im
   * GEKLEMMTEN Schritt stehen.
   * ROT BEI: In zoomViewport die eigene Spannen-Klemme entfernen und das Klemmen
   * clampViewport überlassen — die Spanne stimmt dann noch, aber der Anker springt am
   * Anschlag weg (clampViewport verankert am rechten Rand). Die zweite Zusicherung.
   */
  it("erreicht nach zwanzig Schritten genau MIN_SPAN_MS, und der Anker rutscht am Anschlag nicht weg", () => {
    const anchor = 0.25;
    const start = presetViewport("week");
    const anchorTime = timeAt(start, anchor, NOW);

    let viewport = start;
    for (let step = 0; step < 20; step += 1) {
      viewport = zoomViewport(viewport, 2, anchor, NOW);
    }

    expect(spanOf(viewport, NOW)).toBe(MIN_SPAN_MS);
    expect(Math.abs(timeAt(viewport, anchor, NOW) - anchorTime)).toBeLessThanOrEqual(1);
  });
});

describe("requiredHours", () => {
  /**
   * BELEGT: Der Vertrag der Route (`hours` 1–168) wird von der ABLEITUNG gehalten,
   * nicht von der aufrufenden Stelle — sonst müsste jede künftige Aufrufstelle daran
   * denken. Geprüft über 200 verschiedene Ausschnitte: das Ladefenster deckt den
   * Ausschnitt immer, und der Wert verlässt nie 1…168.
   * ROT BEI: Aufrunden durch Abrunden ersetzen (`findLast(h => h <= benötigt)`) →
   * die Abdeckung. Den Deckel `?? MAX_BACKEND_HOURS` durch `?? Math.ceil(benötigt)`
   * ersetzen → der Vertrag (bei Wochenspanne kämen 202 heraus).
   */
  it("deckt 200 zufällige Ausschnitte immer ab und überschreitet die Backend-Grenze nie", () => {
    const random = makeRandom(20260902);

    for (let index = 0; index < 200; index += 1) {
      const span = MIN_SPAN_MS + random() * (MAX_SPAN_MS - MIN_SPAN_MS);
      const back = random() * (MAX_SPAN_MS - span);
      const viewport = clampViewport(NOW - back - span, NOW - back, NOW);

      const hours = requiredHours(viewport, NOW, 0);
      const { startMs } = resolveViewport(viewport, NOW);

      expect(NOW - hours * HOUR_MS).toBeLessThanOrEqual(startMs);
      expect(hours).toBeGreaterThanOrEqual(1);
      expect(hours).toBeLessThanOrEqual(MAX_BACKEND_HOURS);
    }
  });

  /**
   * BELEGT: Die Stufenleiter verhindert den Abruf-Sturm OHNE Timer — 300 Jetzt-Werte
   * über eine Minute ergeben denselben Wert, im Folge- wie im festen Modus. Dazu die
   * Monotonie: wer nach einem weiten Ausschnitt wieder eng zoomt, verliert das schon
   * geladene Fenster nicht.
   * ROT BEI: Die Leiter durch stufenloses `Math.ceil(benötigt)` ersetzen — im festen
   * Modus wechselt der Wert dann innerhalb derselben Minute (Flackern). `Math.max(
   * previousHours, …)` entfernen → die Monotonie-Zusicherung.
   */
  it("ist über 300 Jetzt-Werte konstant und schrumpft nie unter den zuletzt geholten Wert", () => {
    const follow = presetViewport("shift");
    const frozen = clampViewport(NOW - 15 * HOUR_MS, NOW - 14 * HOUR_MS, NOW);
    const followValues = new Set<number>();
    const frozenValues = new Set<number>();

    for (let tick = 0; tick < 300; tick += 1) {
      const now = NOW + tick * 200;
      followValues.add(requiredHours(follow, now, 0));
      frozenValues.add(requiredHours(frozen, now, 0));
    }

    expect([...followValues]).toEqual([12]);
    expect(frozenValues.size).toBe(1);

    const far = clampViewport(NOW - 100 * HOUR_MS, NOW - 76 * HOUR_MS, NOW);
    const wide = requiredHours(far, NOW, 0);
    expect(wide).toBe(120);
    expect(requiredHours(follow, NOW, wide)).toBe(wide);
  });
});

describe("matchPreset", () => {
  /**
   * BELEGT: Die Schnellwahl ist wirklich ABGELEITET — nach einem freien Zoom ist kein
   * Knopf gedrückt. Die Modus-Zusicherung dazwischen ist die Aufbau-Kontrolle: das
   * `null` kommt aus der Spanne und nicht daher, dass der Ausschnitt festgefroren ist.
   * ROT BEI: In matchPreset die Spannen-Gleichheit weglassen und nur den Modus prüfen —
   * der frei gezoomte Ausschnitt liefert dann trotzdem einen Preset.
   */
  it("liefert nach einem freien Zoom null und nach presetViewport('day') genau 'day'", () => {
    expect(matchPreset(presetViewport("day"), NOW)).toBe("day");
    expect(matchPreset(presetViewport("week"), NOW)).toBe("week");

    const free = zoomViewport(presetViewport("day"), 1.5, 1, NOW);
    expect(free.mode).toBe("follow");
    expect(spanOf(free, NOW)).toBe(16 * HOUR_MS);
    expect(matchPreset(free, NOW)).toBeNull();

    const frozen = clampViewport(NOW - 50 * HOUR_MS, NOW - 26 * HOUR_MS, NOW);
    expect(matchPreset(frozen, NOW)).toBeNull();
  });
});

describe("entartete Eingaben", () => {
  /**
   * BELEGT (zusätzlich zum Plan): Spanne null, verdrehte Grenzen, Faktor null und ein
   * Ankeranteil außerhalb 0…1 liefern einen gültigen, endlichen Ausschnitt. Ein NaN in
   * der Achsen-Domäne zerstört das SVG STILL — kein Fehler, kein Log, nur ein leerer
   * Rahmen; genau deshalb steht hier eine Endlichkeits-Prüfung und keine Momentaufnahme.
   * ROT BEI: `clampSpan` aus clampViewport oder zoomViewport entfernen (Spanne 0 bzw.
   * Division durch 0 schlagen durch); `clampFraction` entfernen (der Anker −1 zieht das
   * Fenster über den Rand hinaus).
   */
  it("liefern gültige, endliche Ausschnitte statt NaN", () => {
    const zero = clampViewport(NOW, NOW, NOW);
    expect(spanOf(zero, NOW)).toBe(MIN_SPAN_MS);

    const inverted = clampViewport(NOW, NOW - HOUR_MS, NOW);
    expect(spanOf(inverted, NOW)).toBe(MIN_SPAN_MS);
    expect(resolveViewport(inverted, NOW).endMs).toBe(NOW - HOUR_MS);

    const noFactor = zoomViewport(presetViewport("day"), 0, 0.5, NOW);
    expect(spanOf(noFactor, NOW)).toBe(MAX_SPAN_MS);

    const belowAnchor = zoomViewport(presetViewport("day"), 2, -1, NOW);
    const aboveAnchor = zoomViewport(presetViewport("day"), 2, 2, NOW);
    expect(timeAt(belowAnchor, 0, NOW)).toBe(NOW - 24 * HOUR_MS);
    expect(timeAt(aboveAnchor, 1, NOW)).toBe(NOW);

    for (const viewport of [zero, inverted, noFactor, belowAnchor, aboveAnchor]) {
      const { startMs, endMs } = resolveViewport(viewport, NOW);
      expect(Number.isFinite(startMs)).toBe(true);
      expect(Number.isFinite(endMs)).toBe(true);
      expect(Number.isFinite(requiredHours(viewport, NOW, 0))).toBe(true);
    }

    expect(describeSpan(0)).toBe("0 Minuten");
    expect(describeSpan(-HOUR_MS)).toBe("0 Minuten");
  });
});

describe("describeSpan / describeViewport", () => {
  /**
   * BELEGT (zusätzlich zum Plan): Der Wortlaut, den Statuszeile und Live-Region
   * vorlesen — Singular und Plural an jeder Einheit, und die Grenzen dazwischen
   * (59 Minuten / 1 Stunde, 23 Stunden / 1 Tag). Eine Ansage „1 Stunden" fällt in
   * einer aria-live-Region jedem Hörer auf und ist nirgends sonst geprüft.
   * ROT BEI: In `plural` Singular und Plural tauschen; in describeSpan die Tages- vor
   * der Stundenstufe entfernen (aus „3 Tage 4 Stunden" würde „76 Stunden").
   */
  it("sprechen deutsch — Singular, Plural und die Grenzen dazwischen", () => {
    expect(describeSpan(BUCKET_MS)).toBe("1 Minute");
    expect(describeSpan(59 * BUCKET_MS)).toBe("59 Minuten");
    expect(describeSpan(HOUR_MS)).toBe("1 Stunde");
    expect(describeSpan(HOUR_MS + BUCKET_MS)).toBe("1 Stunde 1 Minute");
    expect(describeSpan(2 * HOUR_MS + 30 * BUCKET_MS)).toBe("2 Stunden 30 Minuten");
    expect(describeSpan(23 * HOUR_MS)).toBe("23 Stunden");
    expect(describeSpan(24 * HOUR_MS)).toBe("1 Tag");
    expect(describeSpan(3 * 24 * HOUR_MS + 4 * HOUR_MS)).toBe("3 Tage 4 Stunden");
    expect(describeSpan(MAX_SPAN_MS)).toBe("7 Tage");

    expect(describeViewport(presetViewport("shift"), NOW)).toBe(
      "Ausschnitt 8 Stunden bis jetzt, folgt dem Live-Rand",
    );
    expect(describeViewport(clampViewport(NOW - 4 * HOUR_MS, NOW - 2 * HOUR_MS, NOW), NOW)).toBe(
      "Ausschnitt 2 Stunden, steht fest, 2 Stunden hinter dem Live-Rand",
    );
  });
});
