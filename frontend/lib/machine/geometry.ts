// ============================================================
//  FOREMAN Frontend — lib/machine/geometry.ts
//  Zweck: Reine SVG-Geometrie des TimeSeriesChart — lineare Skalen (Zeit→x,
//         Wert→y), Pfad-Bau und die Rasterung der Wert-Domäne. Ohne DOM/Transport,
//         deterministisch testbar.
//         Die ZEIT-Domäne wird vom gewählten Ausschnitt gesetzt (nicht von den
//         Daten) → der Live-Rand wächst rein, ohne dass die Achse springt. Die
//         WERT-Domäne folgt dagegen der sichtbaren Scheibe und läuft deshalb durch
//         `niceDomain` — sonst atmet die Linie beim Schieben senkrecht.
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

/**
 * Zahl der Raster-Schritte, die `niceDomain` über die Domäne legt. Vier statt der
 * andernorts üblichen zehn: Je gröber das Raster, desto seltener wechselt die Domäne
 * beim Schieben — und das Diagramm beschriftet ohnehin nur die beiden Domänen-Enden,
 * braucht also keine Zwischenmarken, für die ein feines Raster gut wäre.
 */
const RASTER_STEPS = 4;

/** Aufschlag um einen einzelnen Wert (Spanne null), relativ zu seinem Betrag. */
const ZERO_SPAN_PAD_RATIO = 0.05;

/** Aufschlag um die Null herum — dort gibt es keinen Betrag, aus dem einer folgen könnte. */
const ZERO_SPAN_PAD_ABS = 0.5;

/**
 * Domäne für Eingaben, aus denen sich keine berechnen lässt. Breite eins, damit
 * `scaleLinear` darauf eine echte Skala liefert statt der Bereichsmitte.
 */
const FALLBACK_DOMAIN: [number, number] = [0, 1];

/** Nächstgrößere Schrittweite aus der Reihe 1/2/5 × 10^n. */
function niceStep(rawStep: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / magnitude;
  if (normalized <= 1) {
    return magnitude;
  }
  if (normalized <= 2) {
    return 2 * magnitude;
  }
  if (normalized <= 5) {
    return 5 * magnitude;
  }
  return 10 * magnitude;
}

/**
 * Rastert einen Wertebereich auf Schritte der Reihe 1/2/5 × 10^n und gibt die
 * umschließende Domäne zurück.
 *
 * Gebaut gegen die senkrecht atmende Linie: Die Wert-Domäne folgt dem sichtbaren
 * Ausschnitt, und ohne Raster ergibt jeder Schiebe-Schritt eine minimal andere
 * Domäne — dieselbe Kurve wandert dann bei jedem Bild ein Stück auf und ab, obwohl
 * sich kein Messwert geändert hat. Zwei benachbarte Eingabebereiche derselben
 * Rasterstufe liefern deshalb ein IDENTISCHES Ergebnis.
 *
 * Zusicherungen, jede mit eigenem Test: Das Ergebnis umschließt die Eingabe, hat nie
 * die Breite null und enthält nie NaN — auch bei vertauschten Grenzen, bei
 * `low === high` (auch auf der Null) und bei nicht endlichen Eingaben.
 */
export function niceDomain(low: number, high: number): [number, number] {
  let lo = Math.min(low, high);
  let hi = Math.max(low, high);

  // Spanne null: ohne Aufschlag bliebe die Domäne null breit, und die Skala läge
  // für jeden Wert auf der Bereichsmitte — eine flache Reihe hätte keine Achse.
  if (lo === hi) {
    const pad = Math.abs(lo) > 0 ? Math.abs(lo) * ZERO_SPAN_PAD_RATIO : ZERO_SPAN_PAD_ABS;
    lo -= pad;
    hi += pad;
  }

  const step = niceStep((hi - lo) / RASTER_STEPS);
  const lower = Math.floor(lo / step) * step;
  const upper = Math.ceil(hi / step) * step;

  // EINE Prüfung für zwei Fälle, weil beide denselben Weg nehmen: Eine nicht endliche
  // Grenze und eine Spanne jenseits des Zahlenbereichs machen die Schrittweite beide
  // nicht endlich, und das Produkt daraus wird NaN. Eine zweite Prüfung auf die
  // EINGABE wäre deshalb nie erreichbar — ein toter Zweig, der Sorgfalt vortäuscht.
  // Ein NaN in der Achsen-Domäne zerstört das SVG STILL: kein Fehler, kein Log, nur
  // ein leerer Rahmen.
  if (!Number.isFinite(lower) || !Number.isFinite(upper)) {
    return FALLBACK_DOMAIN;
  }

  return [lower, upper];
}

/**
 * Baut den geschlossenen Pfad einer Hüllfläche (Min-Max eines Buckets, Bänder):
 * vorwärts entlang der oberen Punkte, rückwärts entlang der unteren, mit `Z`
 * geschlossen. Beide Reihen werden in derselben x-Reihenfolge erwartet.
 *
 * Die Rückwärts-Richtung ist die eigentliche Sache: Hängte man die untere Reihe
 * vorwärts an, liefe der Pfad quer durch die Fläche zurück, und die Hülle würde zur
 * Schleife — gefüllt sähe man eine Figur, die keiner Messung entspricht.
 *
 * Leere obere Reihe → leerer Pfad statt eines `Z` ohne Punkte.
 */
export function envelopePath(upper: readonly Point[], lower: readonly Point[]): string {
  if (upper.length === 0) {
    return "";
  }
  const forward = linePath(upper);
  const back = [...lower]
    .reverse()
    .map((p) => `L${p.x},${p.y}`)
    .join("");
  return `${forward}${back}Z`;
}
