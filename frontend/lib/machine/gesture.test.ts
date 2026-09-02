// ============================================================
//  FOREMAN Frontend — lib/machine/gesture.test.ts
//  Zweck: Sichert die Gestenmathematik des Sensor-Verlaufs — die Handschuh-
//         Schwellen (12 px / 1,5 / Totzone / 40 px) an ihren Grenzen, die
//         Zerlegung des Zwei-Finger-Griffs in Zoom UND Schub, und den Null-Schutz,
//         der in jsdom (jede Messung 0) trägt. Ohne DOM, ohne Layout.
// ============================================================
import { describe, expect, it } from "vitest";

import {
  anchorRatio,
  distance,
  isDoubleTap,
  isHorizontalIntent,
  panFraction,
  pinchIntents,
  pixelsToMs,
  type PointerPair,
} from "./gesture";

/** Ein Zeigerpaar auf einer waagerechten Linie — nur die x-Abstände tragen hier. */
function pair(x1: number, x2: number): PointerPair {
  return [
    { x: x1, y: 0 },
    { x: x2, y: 0 },
  ];
}

/** Plot-Rechteck der Tests: links 0, 1000 breit, 200/200 Polsterung → 600 px Plot. */
const RECT_LEFT = 0;
const RECT_WIDTH = 1000;
const PAD_LEFT = 200;
const PAD_RIGHT = 200;

describe("isHorizontalIntent", () => {
  it("senkrechter Wisch meldet keine Absicht, waagerechter schon (Zwilling)", () => {
    // Belegt: der Daumen-Streifer beim Seiten-Scrollen erzeugt kein Schieben, der
    // waagerechte Zug aber schon. Der Positiv-Zwilling ist Pflicht — ohne ihn
    // belegte der Negativ-Fall nur, dass die Funktion immer false liefert.
    // Rot bei: INTENT_RATIO → 0 (der überwiegend senkrechte Fall gilt als Absicht);
    // INTENT_PX → 100 (der waagerechte Fall meldet nichts mehr).
    expect(isHorizontalIntent(6, 80)).toBe(false);
    expect(isHorizontalIntent(20, 80)).toBe(false);
    expect(isHorizontalIntent(20, 6)).toBe(true);
  });

  it("rechnet in beiden Richtungen mit Beträgen: nach links ja, nach oben nein", () => {
    // Belegt: BEIDE Achsen werden als Betrag gemessen. Der letzte Fall ist der
    // teure — nach oben wischen heißt dy < 0, und ohne Betrag wäre jeder
    // Aufwärts-Wisch mit etwas Wackeln eine waagerechte Absicht, also gekapertes
    // Seiten-Scrollen in genau der Richtung, in der man am häufigsten wischt.
    // Rot bei: Math.abs auf dx entfernt (der Zug nach links meldet nichts mehr);
    // Math.abs auf dy entfernt (der Wisch nach oben meldet fälschlich).
    expect(isHorizontalIntent(-20, 6)).toBe(true);
    expect(isHorizontalIntent(-20, -6)).toBe(true);
    expect(isHorizontalIntent(20, -80)).toBe(false);
  });

  it("Wegschwelle: 11 px nein, genau 12 px nein, 13 px ja", () => {
    // Belegt: INTENT_PX ist eine ausschließende Grenze — genau auf der Schwelle ist
    // noch keine Absicht. Rot bei: `>` zu `>=` im Weg-Vergleich (12 px meldet dann);
    // INTENT_PX auf 20 (13 px meldet nicht mehr).
    expect(isHorizontalIntent(11, 0)).toBe(false);
    expect(isHorizontalIntent(12, 0)).toBe(false);
    expect(isHorizontalIntent(13, 0)).toBe(true);
  });

  it("Übergewicht: 14/10 nein, genau 15/10 nein, 16/10 ja", () => {
    // Belegt: INTENT_RATIO als ausschließende Grenze, geprüft AUF der Grenze
    // (15 = 1,5 × 10) und beidseits daneben. Alle drei Fälle liegen über INTENT_PX,
    // die Wegschwelle kann das Ergebnis also nicht erklären.
    // Rot bei: `>` zu `>=` im Verhältnis-Vergleich (15/10 meldet dann);
    // INTENT_RATIO auf 2 (16/10 meldet nicht mehr).
    expect(isHorizontalIntent(14, 10)).toBe(false);
    expect(isHorizontalIntent(15, 10)).toBe(false);
    expect(isHorizontalIntent(16, 10)).toBe(true);
  });
});

describe("pixelsToMs", () => {
  it("Breite 0 liefert 0 statt NaN — und der halbe Weg die halbe Spanne", () => {
    // Belegt: genau der jsdom-Fall (getBoundingClientRect liefert Nullen). Eine
    // Geste ohne gemessenes Layout bewegt nichts, statt NaN in die Achsen-Domäne zu
    // schreiben — ein NaN dort zerstört das SVG STILL, ohne Fehler und ohne Log.
    // Der zweite Fall ist die Aufbau-Kontrolle: ohne ihn bewiese die Null nur, dass
    // die Funktion immer 0 liefert.
    // Rot bei: Null-Schutz entfernt (erster Fall wird NaN).
    const spanMs = 20 * 60_000;
    expect(pixelsToMs(120, 0, spanMs)).toBe(0);
    expect(Number.isNaN(pixelsToMs(120, 0, spanMs))).toBe(false);
    expect(pixelsToMs(329, 658, 1_200_000)).toBe(600_000);
  });

  it("negative Breite liefert 0, Spanne 0 liefert 0 — beides endlich", () => {
    // Belegt: die entarteten Fälle bleiben endlich. Eine negative Breite kann aus
    // einer Polsterung entstehen, die breiter ist als das Rechteck.
    // Rot bei: `value > 0` zu `value !== 0` im Teiler-Test (negative Breite
    // liefert dann einen Weg in die falsche Richtung).
    expect(pixelsToMs(120, -50, 1_200_000)).toBe(0);
    expect(pixelsToMs(329, 658, 0)).toBe(0);
    expect(Number.isFinite(pixelsToMs(120, -50, 1_200_000))).toBe(true);
  });

  it("behält das Vorzeichen: nach links ziehen ergibt eine negative Spanne", () => {
    // Belegt: die Richtung überlebt die Umrechnung. Rot bei: Math.abs auf dxPx.
    expect(pixelsToMs(-329, 658, 1_200_000)).toBe(-600_000);
  });
});

describe("panFraction", () => {
  it("−120 px auf 600 px Breite sind −0,2; Breite 0 liefert 0", () => {
    // Belegt: der Anteil, den die Gestenfläche nach oben meldet (dx = −120 bei
    // surfaceWidthPx = 600 → onPan(−0.2)), plus derselbe Null-Schutz.
    // Rot bei: Null-Schutz entfernt (zweiter Fall wird NaN); Vorzeichen gedreht.
    expect(panFraction(-120, 600)).toBe(-0.2);
    expect(panFraction(120, 0)).toBe(0);
    expect(Number.isNaN(panFraction(120, 0))).toBe(false);
  });
});

describe("anchorRatio", () => {
  it("0 am linken Plotrand, 0,5 in der Mitte, 1 am rechten", () => {
    // Belegt: der Anker ist ein ANTEIL der Zeichenfläche, die Polsterung also
    // abgezogen — sonst verankert ein Finger am linken Plotrand bei 0,06 statt 0.
    // Rot bei: padLeft nicht abgezogen; durch rectWidth statt durch die Plotbreite
    // geteilt (dann ist die Mitte nicht mehr 0,5).
    expect(anchorRatio(144, 100, 720, 44, 16)).toBe(0);
    expect(anchorRatio(474, 100, 720, 44, 16)).toBe(0.5);
    expect(anchorRatio(804, 100, 720, 44, 16)).toBe(1);
  });

  it("außerhalb der Zeichenfläche wird auf 0..1 geklemmt", () => {
    // Belegt: ein Finger auf der Achsenbeschriftung oder neben dem Panel verankert
    // am Rand, nicht außerhalb des Bildes — sonst zoomt die Ansicht an einen
    // Zeitpunkt, den niemand sieht.
    // Rot bei: eine der beiden Klemmen entfernt.
    expect(anchorRatio(0, 100, 720, 44, 16)).toBe(0);
    expect(anchorRatio(5000, 100, 720, 44, 16)).toBe(1);
  });

  it("entartetes Rechteck liefert die Mitte, nie NaN", () => {
    // Belegt: der jsdom-Fall und der Fall, in dem die Polsterung breiter ist als
    // das Rechteck. Die Mitte ist der neutrale Anker und endlich.
    // Rot bei: Null-Schutz entfernt (0/0 → NaN).
    expect(anchorRatio(500, 0, 0, 0, 0)).toBe(0.5);
    expect(anchorRatio(500, 0, 60, 44, 16)).toBe(0.5);
    expect(Number.isNaN(anchorRatio(500, 0, 0, 0, 0))).toBe(false);
  });
});

describe("distance", () => {
  it("misst den Abstand zweier Zeiger; derselbe Punkt ergibt 0", () => {
    // Belegt: 3-4-5. Rot bei: eine der beiden Achsen im Abstand vergessen.
    expect(distance({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5);
    expect(distance({ x: 7, y: 7 }, { x: 7, y: 7 })).toBe(0);
  });
});

describe("pinchIntents", () => {
  it("Totzone: Verhältnis 1,05 zoomt nicht, 1,25 zoomt", () => {
    // Belegt: zwei aufgelegte Knöchel sind zwei Zeiger — ohne Totzone wäre jedes
    // Abstützen mit Handschuh ein Zoom. Der 1,25-Fall ist die Aufbau-Kontrolle:
    // ohne ihn bewiese die 1 nur, dass die Funktion nie zoomt.
    // Rot bei: PINCH_DEADZONE → 0 (der 1,05-Fall liefert dann einen Faktor ≠ 1).
    const start = pair(300, 400); // Abstand 100
    expect(
      pinchIntents(start, pair(297.5, 402.5), RECT_LEFT, RECT_WIDTH, PAD_LEFT, PAD_RIGHT).factor,
    ).toBe(1);
    expect(
      pinchIntents(start, pair(287.5, 412.5), RECT_LEFT, RECT_WIDTH, PAD_LEFT, PAD_RIGHT).factor,
    ).toBe(1.25);
  });

  it("Totzonen-Grenzen: genau 1,1 und genau 0,9 zoomen nicht, knapp daneben schon", () => {
    // Belegt: die Totzone ist das GESCHLOSSENE Intervall [0,9 … 1,1], geprüft auf
    // beiden Grenzen und je einen Schritt daneben. Ohne die Grenzfälle wäre der
    // Wert von PINCH_DEADZONE nur ein Kommentar.
    // Rot bei: `>=`/`<=` zu `>`/`<` (die Grenzfälle zoomen dann);
    // PINCH_DEADZONE → 0.2 (die beiden Fälle daneben zoomen nicht mehr).
    const start = pair(300, 400); // Abstand 100
    const at = (x1: number, x2: number) =>
      pinchIntents(start, pair(x1, x2), RECT_LEFT, RECT_WIDTH, PAD_LEFT, PAD_RIGHT).factor;
    expect(at(295, 405)).toBe(1); // Abstand 110 → Verhältnis 1,1
    expect(at(294.5, 405.5)).toBeCloseTo(1.11, 10); // 111 → 1,11
    expect(at(305, 395)).toBe(1); // 90 → 0,9
    expect(at(305.5, 394.5)).toBeCloseTo(0.89, 10); // 89 → 0,89
  });

  it("liefert Zoom UND Schub: reine Mittelpunkt-Verschiebung ergibt Faktor 1 und einen Schub ≠ 0", () => {
    // Belegt: die WEICHE WAND an ihrer Wurzel. Weil der Griff auch schiebt, bleibt
    // die Geste am Zoom-Boden lebendig, statt tot zu wirken — kein Sonderfall im
    // geklemmten Zweig nötig. Der Anker steht dabei auf dem STARTMITTELPUNKT
    // (Anteil 0), nicht auf dem aktuellen (der ergäbe 0,5): die Wanderung des
    // Mittelpunkts steckt schon im Schub und darf nicht doppelt zählen.
    // Rot bei: die Mittelpunkt-Verschiebung aus pinchIntents streichen (Schub 0);
    // den Anker aus dem AKTUELLEN Mittelpunkt ziehen (Anker 0,5 statt 0).
    const intents = pinchIntents(
      pair(100, 300), // Mitte 200, Abstand 200
      pair(400, 600), // Mitte 500, Abstand 200
      RECT_LEFT,
      RECT_WIDTH,
      PAD_LEFT,
      PAD_RIGHT,
    );
    expect(intents.factor).toBe(1);
    expect(intents.panFraction).toBe(0.5); // 300 px von 600 px Plotbreite
    expect(intents.panFraction).not.toBe(0);
    expect(intents.anchorFraction).toBe(0);
  });

  it("Zwei Zeiger auf demselben Punkt: Faktor 1 statt NaN", () => {
    // Belegt: der entartete Griff (0/0). Ohne Schutz stünde NaN als Zoom-Faktor in
    // der Spanne, und die Zeitachse wäre still zerstört.
    // Rot bei: den Abstands-Null-Schutz entfernen.
    const intents = pinchIntents(
      pair(200, 200),
      pair(150, 250),
      RECT_LEFT,
      RECT_WIDTH,
      PAD_LEFT,
      PAD_RIGHT,
    );
    expect(intents.factor).toBe(1);
    expect(Number.isNaN(intents.factor)).toBe(false);
  });

  it("entartetes Rechteck: Schub 0 und Anker Mitte, der Faktor bleibt echt", () => {
    // Belegt: ohne gemessenes Rechteck (jsdom) bewegt die Geste nichts und alle drei
    // Zahlen bleiben endlich — der Zoom-Faktor braucht das Rechteck aber gar nicht
    // und wird deshalb NICHT mit auf 1 gesetzt.
    // Rot bei: Null-Schutz in panFraction/anchorRatio entfernt (NaN statt 0 / 0,5).
    const intents = pinchIntents(pair(300, 400), pair(287.5, 412.5), 0, 0, 0, 0);
    expect(intents.panFraction).toBe(0);
    expect(intents.anchorFraction).toBe(0.5);
    expect(intents.factor).toBe(1.25);
    expect(Number.isFinite(intents.factor)).toBe(true);
    expect(Number.isFinite(intents.panFraction)).toBe(true);
    expect(Number.isFinite(intents.anchorFraction)).toBe(true);
  });
});

describe("isDoubleTap", () => {
  it("ohne vorherige Berührung nie ein Doppeltipp; dicht beieinander schon", () => {
    // Belegt: der Anfangszustand (noch nichts getippt) plus die Aufbau-Kontrolle.
    // Rot bei: den null-Zweig entfernen; die Zeit- oder Weg-Bedingung streichen.
    expect(isDoubleTap(null, 1_000, 200, 200)).toBe(false);
    expect(isDoubleTap(1_000, 1_150, 200, 220)).toBe(true);
  });

  it("Zeitgrenze: 299 ms ja, genau 300 ms nein, 301 ms nein", () => {
    // Belegt: DOUBLE_TAP_MS als ausschließende Grenze, auf der Grenze und beidseits.
    // Rot bei: `<` zu `<=` (300 ms zählt dann); DOUBLE_TAP_MS auf 200 (299 ms nicht).
    expect(isDoubleTap(1_000, 1_299, 200, 200)).toBe(true);
    expect(isDoubleTap(1_000, 1_300, 200, 200)).toBe(false);
    expect(isDoubleTap(1_000, 1_301, 200, 200)).toBe(false);
  });

  it("Weggrenze mit Handschuh: 30 px und 39 px ja, genau 40 px nein, 41 px nein", () => {
    // Belegt: DOUBLE_TAP_PX ist bewusst 40 statt der sonst üblichen 24 — mit
    // Arbeitshandschuh landet die zweite Berührung leicht 30 bis 40 px neben der
    // ersten. Der 30-px-Fall ist genau der, der beim „Aufräumen“ auf 24 verloren
    // ginge, und er hat deshalb eine eigene Zusicherung.
    // Rot bei: DOUBLE_TAP_PX auf 24 (der 30-px-Fall wird false); `<` zu `<=`
    // (genau 40 px zählt dann).
    expect(isDoubleTap(1_000, 1_100, 200, 230)).toBe(true);
    expect(isDoubleTap(1_000, 1_100, 200, 239)).toBe(true);
    expect(isDoubleTap(1_000, 1_100, 200, 240)).toBe(false);
    expect(isDoubleTap(1_000, 1_100, 200, 241)).toBe(false);
  });

  it("misst den Weg als Betrag; eine rückwärts laufende Uhr ist keine Folge", () => {
    // Belegt: die zweite Berührung darf links der ersten liegen (35 px), aber 100 px
    // links ist keiner mehr — der WEITE Fall ist der tragende: ohne Betrag wäre
    // jede noch so ferne Berührung links der ersten ein Doppeltipp, und ein Tipp
    // auf das andere Ende des Panels zoomte plötzlich. Der nahe Fall allein bliebe
    // auch ohne Betrag grün (−35 < 40) und belegte deshalb nichts.
    // Dazu: ein Zeitwert VOR dem gemerkten Tipp macht keine beliebige Berührung
    // zum Doppeltipp.
    // Rot bei: Math.abs im Weg-Vergleich entfernt (der 100-px-Fall wird true);
    // den `elapsedMs >= 0`-Zweig entfernen (der Rückwärts-Fall zählt dann).
    expect(isDoubleTap(1_000, 1_100, 200, 165)).toBe(true);
    expect(isDoubleTap(1_000, 1_100, 200, 100)).toBe(false);
    expect(isDoubleTap(1_000, 900, 200, 200)).toBe(false);
  });
});
