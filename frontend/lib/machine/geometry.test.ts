// ============================================================
//  FOREMAN Frontend — lib/machine/geometry.test.ts
//  Zweck: Sichert die reine SVG-Geometrie (lineare Skalen, Pfad-Bau, Rasterung der
//         Wert-Domäne, Hüllfläche) des TimeSeriesChart — ohne DOM testbar,
//         deterministisch. Jeder Test nennt, WAS er belegt und WELCHE Mutation im
//         Quelltext ihn rot machen muss.
// ============================================================
import { describe, expect, it } from "vitest";

import { envelopePath, linePath, niceDomain, scaleLinear } from "./geometry";

/**
 * Deterministischer Zufall für die Streuprobe. Ein echter `Math.random()` würde einen
 * Fehlschlag unwiederholbar machen — man wüsste dann nicht, welche Eingabe ihn ausgelöst hat.
 */
function makeRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 0x1_0000_0000;
  };
}

describe("scaleLinear", () => {
  it("bildet Domänen-Enden auf Bereichs-Enden ab", () => {
    const s = scaleLinear([0, 10], [0, 100]);
    expect(s(0)).toBe(0);
    expect(s(10)).toBe(100);
    expect(s(5)).toBe(50);
  });

  it("unterstützt invertierten Bereich (Y-Achse: großer Wert → kleines y)", () => {
    const s = scaleLinear([0, 10], [200, 0]);
    expect(s(0)).toBe(200);
    expect(s(10)).toBe(0);
    expect(s(5)).toBe(100);
  });

  it("entartete Domäne (min == max) → Bereichsmitte statt NaN", () => {
    const s = scaleLinear([5, 5], [0, 100]);
    expect(s(5)).toBe(50);
    expect(Number.isNaN(s(99))).toBe(false);
  });
});

describe("linePath", () => {
  it("baut einen M/L-Pfad aus Punkten", () => {
    expect(
      linePath([
        { x: 0, y: 0 },
        { x: 10, y: 20 },
        { x: 20, y: 5 },
      ]),
    ).toBe("M0,0L10,20L20,5");
  });

  it("leere Punktliste → leerer Pfad", () => {
    expect(linePath([])).toBe("");
  });
});

describe("niceDomain", () => {
  /**
   * Belegt: die Anti-Zitter-Eigenschaft. Nicht „gibt Zahlen zurück", sondern die
   * GLEICHHEIT zweier Ergebnisse bei benachbarten Eingaben — genau das verhindert,
   * dass die Linie beim Schieben senkrecht atmet, obwohl sich kein Messwert ändert.
   * Rot bei: `niceDomain` zur Identität machen (`return [low, high]`) — dann
   * unterscheiden sich die beiden Ergebnisse.
   */
  it("zwei leicht verschiedene Wertebereiche derselben Stufe ergeben eine IDENTISCHE Domäne", () => {
    const a = niceDomain(20.3, 71.8);
    const b = niceDomain(20.9, 72.4);

    expect(a).toEqual(b);
    // Kontrolle des Aufbaus: die Eingaben sind wirklich verschieden, der Vergleich
    // oben belegt also die Rasterung und nicht bloß zweimal dieselbe Rechnung.
    expect(20.3).not.toBe(20.9);
  });

  /**
   * Belegt: die Schrittweite stammt wirklich aus der Reihe 1/2/5 × 10^n. Ein Fall je
   * Sprosse, und jeder liegt so, dass die BENACHBARTE Sprosse ein anderes Ergebnis
   * ergäbe — sonst belegte der Test nur, dass irgendein Raster wirkt. Der erste Fall
   * sitzt genau auf der Grenze (Spanne/4 = 10, also normalisiert exakt 1).
   * Rot bei: jede einzelne Sprossen-Grenze in `niceStep` verschieben — `<= 1` zu
   * `<= 0.9` rötet Fall 1, `<= 1` zu `<= 1.5` rötet Fall 2, `<= 2` zu `<= 3` rötet
   * Fall 3, `<= 5` zu `<= 6` rötet Fall 4.
   */
  it("rastert auf 1/2/5 × 10^n — je ein Fall auf jeder Sprosse", () => {
    expect(niceDomain(63, 103)).toEqual([60, 110]); // Spanne 40 → Schritt 10 (Sprosse 1)
    expect(niceDomain(41, 88)).toEqual([40, 100]); // Spanne 47 → Schritt 20 (Sprosse 2)
    expect(niceDomain(63, 163)).toEqual([50, 200]); // Spanne 100 → Schritt 50 (Sprosse 5)
    expect(niceDomain(63, 283)).toEqual([0, 300]); // Spanne 220 → Schritt 100 (Sprosse 10)
  });

  /**
   * Belegt: das Ergebnis UMSCHLIESST die Eingabe, über zwölf Größenordnungen hinweg —
   * eine Domäne, die knapp innerhalb der Daten endet, schneidet genau die Spitze ab,
   * wegen der jemand hinsieht. Zusätzlich: nie NaN, nie die Breite null.
   * Rot bei: `Math.floor` für die Untergrenze durch `Math.ceil` ersetzen (oder
   * umgekehrt `Math.ceil` durch `Math.floor` oben) — die Umschließung fällt.
   */
  it("umschließt 200 gestreute Wertebereiche und liefert nie NaN oder Breite null", () => {
    const random = makeRandom(20260902);
    const verstoesse: string[] = [];

    for (let i = 0; i < 200; i += 1) {
      const exponent = Math.floor(random() * 12) - 6;
      const base = (random() - 0.5) * 10 ** exponent;
      const width = random() * 10 ** exponent;
      const [lo, hi] = niceDomain(base, base + width);

      if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
        verstoesse.push(`nicht endlich: [${base}, ${base + width}] → [${lo}, ${hi}]`);
        continue;
      }
      if (hi <= lo) {
        verstoesse.push(`Breite null: [${base}, ${base + width}] → [${lo}, ${hi}]`);
      }
      if (lo > base || hi < base + width) {
        verstoesse.push(`schneidet ab: [${base}, ${base + width}] → [${lo}, ${hi}]`);
      }
    }

    expect(verstoesse).toEqual([]);
  });

  /**
   * Belegt: `low === high` (die flache Reihe) ergibt eine Domäne mit echter Breite,
   * die den Wert enthält — auf der Null, im Positiven und im Negativen. Ohne Aufschlag
   * bliebe die Domäne null breit, `scaleLinear` legte jeden Wert auf die Bereichsmitte,
   * und der Sensor hätte gar keine Achse.
   * Rot bei: den Aufschlag-Zweig (`lo === hi`) entfernen — alle drei Breiten werden null.
   */
  it("Spanne null: Domäne bleibt echt breit und enthält den Wert — bei 0, positiv und negativ", () => {
    for (const wert of [0, 42, -7]) {
      const [lo, hi] = niceDomain(wert, wert);

      expect(Number.isNaN(lo)).toBe(false);
      expect(Number.isNaN(hi)).toBe(false);
      expect(hi).toBeGreaterThan(lo);
      expect(lo).toBeLessThanOrEqual(wert);
      expect(hi).toBeGreaterThanOrEqual(wert);
    }
  });

  /**
   * Belegt: vertauschte Grenzen liefern dieselbe Domäne wie sortierte. Die sichtbare
   * Scheibe wird aus mehreren Quellen zusammengezogen (Messwerte, Normalband,
   * Eigenprofil); welche davon die kleinere ist, weiß die aufrufende Stelle nicht.
   * Rot bei: `Math.min`/`Math.max` durch die rohen Argumente ersetzen — die
   * vertauschte Eingabe ergibt dann eine andere (oder eine unsinnige) Domäne.
   */
  it("vertauschte Grenzen ergeben dieselbe Domäne wie sortierte", () => {
    expect(niceDomain(71.8, 20.3)).toEqual(niceDomain(20.3, 71.8));
    expect(niceDomain(-10, -50)).toEqual(niceDomain(-50, -10));
  });

  /**
   * Belegt: eine sehr kleine Spanne wird nicht auf null gerastert. Bei 20 Minuten
   * Ausschnitt liegt genau so ein Bereich vor — ein bis auf die vierte Stelle
   * konstanter Sensor. Fiele die Domäne dort zusammen, wäre der tiefste Zoomgrad
   * ausgerechnet der einzige ohne Achse.
   * Rot bei: die Schrittweite auf eine feste Größe (etwa 1) setzen, statt sie aus der
   * Spanne abzuleiten — die Domäne wird dann [1, 2] statt eng um die Daten.
   */
  it("sehr kleine Spanne behält eine passende Domäne", () => {
    const [lo, hi] = niceDomain(1, 1.0001);

    expect(hi).toBeGreaterThan(lo);
    expect(lo).toBeLessThanOrEqual(1);
    expect(hi).toBeGreaterThanOrEqual(1.0001);
    expect(hi - lo).toBeLessThan(0.01);
  });

  /**
   * Belegt: nicht endliche Grenzen ergeben eine brauchbare Ersatz-Domäne statt NaN.
   * Ein NaN in der Achsen-Domäne zerstört das SVG STILL — kein Fehler, kein Log, nur
   * ein leerer Rahmen; `Infinity` gehört dabei zum normalen Betrieb, weil eine
   * Min/Max-Schleife über eine LEERE sichtbare Scheibe genau ihre Startwerte behält.
   * Rot bei: die Endlichkeits-Prüfung nach der Rechnung entfernen — jeder Fall
   * liefert dann [NaN, NaN].
   */
  it("nicht endliche Grenzen → Ersatz-Domäne, nie NaN", () => {
    for (const paar of [
      [Number.NaN, 5],
      [5, Number.NaN],
      [Number.NaN, Number.NaN],
      [Number.POSITIVE_INFINITY, 1],
      [-1, Number.NEGATIVE_INFINITY],
      [Number.NEGATIVE_INFINITY, Number.POSITIVE_INFINITY],
      [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY],
    ] as const) {
      const [lo, hi] = niceDomain(paar[0], paar[1]);

      expect(Number.isFinite(lo)).toBe(true);
      expect(Number.isFinite(hi)).toBe(true);
      expect(hi).toBeGreaterThan(lo);
    }
  });

  /**
   * Belegt: auch zwei ENDLICHE Grenzen können eine Spanne aufspannen, die im
   * Zahlenbereich nicht mehr Platz hat — die Schrittweite wird unendlich, das Produkt
   * daraus NaN. Der Fall ist der Grund, warum die Prüfung NACH der Rechnung steht: Vor
   * ihr sehen diese Eingaben endlich aus.
   * Rot bei: dieselbe Prüfung entfernen — beide Fälle liefern [NaN, NaN].
   */
  it("Überlauf trotz endlicher Grenzen → Ersatz-Domäne, nie NaN", () => {
    for (const paar of [
      [1e308, -1e308],
      [Number.MAX_VALUE, Number.MAX_VALUE],
    ] as const) {
      const [lo, hi] = niceDomain(paar[0], paar[1]);

      expect(Number.isNaN(lo)).toBe(false);
      expect(Number.isNaN(hi)).toBe(false);
      expect(Number.isFinite(lo)).toBe(true);
      expect(Number.isFinite(hi)).toBe(true);
      expect(hi).toBeGreaterThan(lo);
    }
  });
});

describe("envelopePath", () => {
  const oben = [
    { x: 0, y: 10 },
    { x: 10, y: 12 },
    { x: 20, y: 8 },
  ];
  const unten = [
    { x: 0, y: 20 },
    { x: 10, y: 22 },
    { x: 20, y: 18 },
  ];

  /**
   * Belegt: die Hülle läuft vorwärts über die obere Reihe und RÜCKWÄRTS über die
   * untere, geschlossen mit `Z`. Geprüft wird die ausgegebene Zeichenkette, nicht die
   * Zahl der Punkte — hängte man die untere Reihe vorwärts an, wäre die Punktzahl
   * dieselbe und die gefüllte Figur trotzdem eine Schleife.
   * Rot bei: `.reverse()` entfernen — die untere Hälfte erscheint dann als
   * `L0,20L10,22L20,18`.
   */
  it("läuft vorwärts oben, rückwärts unten und schließt mit Z", () => {
    expect(envelopePath(oben, unten)).toBe("M0,10L10,12L20,8L20,18L10,22L0,20Z");
  });

  /**
   * Belegt: der Pfad ist wirklich GESCHLOSSEN. Ohne `Z` malt der Browser bei
   * `fill` zwar dieselbe Fläche, die Kontur bleibt aber offen — ein `stroke` auf der
   * Hülle zeigte dann eine Kante zu wenig.
   * Rot bei: das abschließende `Z` weglassen.
   */
  it("endet auf Z", () => {
    expect(envelopePath(oben, unten).endsWith("Z")).toBe(true);
  });

  /**
   * Belegt: ohne obere Punkte entsteht KEIN Pfad. Ein `Z` ohne vorangehendes `M` ist
   * für den Browser kein Fehler, sondern ein stiller Nichts-Pfad — er fiele erst auf,
   * wenn jemand die leere Fläche für ein fehlendes Band hält.
   * Rot bei: die Leer-Prüfung entfernen — das Ergebnis ist dann `"Z"`.
   */
  it("leere obere Reihe → leerer Pfad", () => {
    expect(envelopePath([], unten)).toBe("");
  });

  /**
   * Belegt: eine leere UNTERE Reihe kappt den Pfad nicht, sondern liefert die obere
   * Linie geschlossen zurück. Das ist der Fall „Bucket ohne Min/Max" — die Hülle
   * schrumpft dann auf die Linie, statt zu verschwinden.
   * Rot bei: die Leer-Prüfung auf beide Reihen ausweiten — das Ergebnis wird `""`.
   */
  it("leere untere Reihe → geschlossene obere Linie", () => {
    expect(envelopePath(oben, [])).toBe("M0,10L10,12L20,8Z");
  });

  /**
   * Belegt: ein einzelner Bucket (je ein Punkt oben und unten) ergibt eine Hülle mit
   * genau diesen beiden Punkten. Der tiefste Zoomgrad kann bis auf einen Messwert
   * herunterkommen; eine Sonderbehandlung für „zu wenige Punkte" gibt es nicht.
   * Rot bei: eine Mindestlänge (etwa `upper.length < 2`) in die Leer-Prüfung nehmen.
   */
  it("ein einzelner Punkt je Reihe ergibt eine zweipunktige Hülle", () => {
    expect(envelopePath([{ x: 5, y: 1 }], [{ x: 5, y: 9 }])).toBe("M5,1L5,9Z");
  });
});
