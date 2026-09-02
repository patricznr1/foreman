// ============================================================
//  FOREMAN Frontend — lib/machine/use-time-viewport.test.ts
//  Zweck: Sichert die drei Zusicherungen, die erst in der BINDUNG entstehen und
//         die keine der reinen Funktionen aus viewport.ts halten kann:
//         (1) `hours` ist monoton — Hineinzoomen verwirft den schon geholten
//             Rand nicht; (2) Schnellwahl und `Jetzt` setzen genau diese
//             Monotonie zurück, sonst bleibt die Sitzung auf der höchsten
//             einmal erreichten Sprosse hängen; (3) die Live-Region spricht am
//             GESTENENDE und bei Knopf-Befehlen, nicht bei jedem Bild.
//         Kein Timer, kein Fake-Timer, kein DOM-Layout: `nowMs` wird
//         eingespritzt (Bauform von `useMachineTrend`), jede Zusicherung ist
//         eine Gleichheit von Zahlen oder von Text.
//         Jeder Test nennt, WAS er belegt und WELCHE Mutation ihn rot macht.
// ============================================================
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MAX_BACKEND_HOURS } from "./time-window";
import { useTimeViewport } from "./use-time-viewport";
import { describeViewport, presetViewport, resolveViewport } from "./viewport";

import type { TrendViewport } from "./viewport";

const NOW = Date.parse("2026-06-17T12:00:00Z");

/** Der Ausschnitt beim ersten Bild — Vergleichsanker für die Ansage. */
const START = presetViewport("day");

function starte() {
  return renderHook(() => useTimeViewport({ nowMs: NOW }));
}

/** Spanne des aufgelösten Ausschnitts (spart die Union-Verzweigung im Test). */
function spanOf(viewport: TrendViewport): number {
  const { startMs, endMs } = resolveViewport(viewport, NOW);
  return endMs - startMs;
}

describe("useTimeViewport — das Ladefenster", () => {
  it("hours ist monoton: nach einem Schub in die Vergangenheit gibt Hineinzoomen den geholten Rand nicht zurück", () => {
    // BELEGT: Der Kern der Bindung. `requiredHours` bekommt den zuletzt geholten
    // Wert als Untergrenze; ohne ihn fordert jedes Hineinzoomen ein KLEINERES
    // Ladefenster an, und der bereits gezeichnete Rand fiele wieder heraus.
    // MUTATION, die rot werden muss: in `tracked` statt `previous.hours` eine 0
    // an `requiredHours` geben — dann fällt der Wert nach dem Zoom auf 48.
    const { result } = starte();
    expect(result.current.hours).toBe(48); // 24 h Ausschnitt × 1.2 → Sprosse 48

    act(() => {
      result.current.pan(-1);
    });
    const nachSchub = result.current.hours;
    expect(nachSchub).toBe(72); // 48 h Abstand × 1.2 = 57.6 → Sprosse 72

    act(() => {
      result.current.zoom(8, 0.5);
    });
    // Der Ausschnitt ist jetzt 3 h breit und bräuchte für sich genommen 48 h.
    expect(spanOf(result.current.viewport)).toBe(3 * 60 * 60 * 1000);
    expect(result.current.hours).toBe(72);
    expect(result.current.hours).toBeGreaterThanOrEqual(nachSchub);
  });

  it("Schnellwahl setzt die Monotonie zurück — sonst bleibt die Sitzung auf der höchsten Sprosse", () => {
    // BELEGT: Der Ausweg aus der Monotonie. Ohne ihn zahlt jeder Nutzer, der
    // einmal weit zurückgeschoben hat, für den Rest der Sitzung das volle
    // Ladefenster — auch für einen 8-Stunden-Blick auf den Live-Rand.
    // MUTATION: in `quickPick` `previous.hours` statt 0 an `commanded` geben —
    // dann bleibt hours auf 72.
    const { result } = starte();
    act(() => {
      result.current.pan(-1);
    });
    expect(result.current.hours).toBe(72);

    act(() => {
      result.current.quickPick("shift");
    });
    expect(result.current.hours).toBe(12); // 8 h × 1.2 = 9.6 → Sprosse 12
    expect(result.current.following).toBe(true);
  });

  it("„Jetzt“ kehrt an den Live-Rand zurück, behält die Spanne und setzt die Monotonie zurück", () => {
    // BELEGT: Drei Dinge in einem Befehl — der Folge-Modus wird wieder erreicht
    // (er ist abgeleitet, nicht gesetzt), die Spanne des Ausschnitts überlebt den
    // Sprung, und das Ladefenster schrumpft wieder auf das Nötige.
    // MUTATION 1: in `toNow` `previous.hours` statt 0 → hours bliebe 72, rot.
    // MUTATION 2: in `toNow` den rechten Rand nicht auf `now` setzen (etwa
    // `clampViewport(now - span, now - span / 2, now)`) → `following` wird false, rot.
    const { result } = starte();
    act(() => {
      result.current.pan(-1);
      result.current.zoom(8, 0.5);
    });
    const spanneVorher = spanOf(result.current.viewport);
    expect(result.current.following).toBe(false);
    expect(result.current.hours).toBe(72);

    act(() => {
      result.current.toNow();
    });
    expect(result.current.following).toBe(true);
    expect(spanOf(result.current.viewport)).toBe(spanneVorher);
    expect(result.current.hours).toBe(4); // 3 h × 1.2 = 3.6 → Sprosse 4
  });

  it("„Ältester Verlauf“ schiebt das GANZE Fenster an die 7-Tage-Wand, ohne die Spanne zu stauchen", () => {
    // BELEGT: Der Sprung an den Anschlag verändert nur die Position, nicht die
    // Auflösung — sonst würde das Bild an der Wand stillschweigend feiner,
    // obwohl niemand gezoomt hat. Und das Ladefenster erreicht dabei den Deckel
    // der Route statt ihn zu überschreiten.
    // MUTATION: in `toOldest` `clampViewport(wall, endMs, now)` statt
    // `clampViewport(wall, wall + span, now)` — die Spanne wächst auf 168 h, rot.
    const { result } = starte();
    const spanneVorher = spanOf(result.current.viewport);

    act(() => {
      result.current.toOldest();
    });
    expect(result.current.atWall).toBe(true);
    expect(spanOf(result.current.viewport)).toBe(spanneVorher);
    expect(result.current.hours).toBe(MAX_BACKEND_HOURS);
  });
});

describe("useTimeViewport — die Ansage", () => {
  it("zehn Schübe ändern die Ansage nicht, das Gestenende ändert sie genau einmal", () => {
    // BELEGT: Eine aria-live-Zeile, die bildweise feuert, ist für Screenreader
    // schlimmer als gar keine Ansage — und in einer SEHENDEN Durchsicht fällt das
    // niemandem auf. Gezählt wird hier die Zahl der Textwechsel selbst, denn die
    // Zahl IST die Zusicherung. Kein Fake-Timer nötig: die Ansage hängt an einem
    // Ereignis, nicht an einer Entprellung.
    // MUTATION 1: die Ansage in `tracked` mitschreiben → zehn Wechsel, rot.
    // MUTATION 2: `announcement` in `initialState` mit `describeViewport` füllen →
    // die Zusicherung „beim ersten Bild schweigt sie“ wird rot.
    const { result } = starte();
    expect(result.current.announcement).toBe("");

    const gesehen: string[] = [];
    for (let schritt = 0; schritt < 10; schritt += 1) {
      act(() => {
        result.current.pan(-0.1);
      });
      gesehen.push(result.current.announcement);
    }
    expect(gesehen.filter((text) => text !== "")).toHaveLength(0);

    act(() => {
      result.current.endGesture();
    });
    expect(result.current.announcement).toBe(describeViewport(result.current.viewport, NOW));
    expect(result.current.announcement).not.toBe("");
  });

  it("Ein Knopf, der im selben Ereignis schiebt und abschließt, sagt den NEUEN Ausschnitt an", () => {
    // BELEGT: Die Knöpfe `−` / `+` / `Älter` / `Neuer` laufen über dieselben
    // Befehle wie die Geste und schließen mit `endGesture()` ab — beides im
    // selben Ereignis. Läse `endGesture` den Ausschnitt aus dem Renderdurchlauf
    // statt aus dem Zustands-Vorgänger, spräche die Ansage über das Bild VOR dem
    // Knopfdruck: sie sagte „folgt dem Live-Rand“, während das Bild feststeht.
    // MUTATION: in `endGesture` `state.viewport` (der Wert des Renderdurchlaufs)
    // statt `previous.viewport` verwenden → die Ansage beschreibt den alten
    // Ausschnitt, beide Zusicherungen werden rot.
    const { result } = starte();

    act(() => {
      result.current.pan(-0.5);
      result.current.endGesture();
    });

    expect(result.current.announcement).toBe(describeViewport(result.current.viewport, NOW));
    expect(result.current.announcement).not.toBe(describeViewport(START, NOW));
  });
});

describe("useTimeViewport — die abgeleiteten Marken", () => {
  it("atFloor, following und description folgen dem AKTUELLEN Ausschnitt, nicht dem ersten", () => {
    // BELEGT: Die Marken, aus denen die Knöpfe ihr `disabled` und die Statuszeile
    // ihren Text ziehen, werden bei jedem Bild neu aus dem Ausschnitt abgeleitet.
    // Ein mitgeführter Schalter (useState/useRef beim ersten Bild gefüllt) wäre
    // die klassische zweite Wahrheit: der Hineinzoomen-Knopf bliebe am Boden
    // bedienbar und die Statuszeile nennte weiter „1 Tag“.
    // MUTATION: `atFloor`/`description` aus einem beim ersten Bild gespeicherten
    // Ausschnitt ableiten statt aus `state.viewport` → beide Zusicherungen rot.
    const { result } = starte();
    expect(result.current.atFloor).toBe(false);
    expect(result.current.description).toContain("1 Tag");

    act(() => {
      result.current.zoom(1000, 0.5);
    });
    expect(result.current.atFloor).toBe(true);
    expect(result.current.following).toBe(false);
    expect(result.current.description).toContain("20 Minuten");
  });
});
