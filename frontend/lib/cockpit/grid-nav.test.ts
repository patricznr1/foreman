// ============================================================
//  FOREMAN Frontend — lib/cockpit/grid-nav.test.ts
//  Zweck: Sichert die reine Tastatur-Navigation der Heatmap-Matrix bei variabler
//         Spaltenzahl je Zeile (geklemmt, kein Umlauf).
// ============================================================
import { describe, expect, it } from "vitest";

import { isGridKey, moveFocus } from "./grid-nav";

describe("isGridKey", () => {
  it("erkennt Navigationstasten und reicht andere durch", () => {
    expect(isGridKey("ArrowRight")).toBe(true);
    expect(isGridKey("Home")).toBe(true);
    expect(isGridKey("Enter")).toBe(false);
    expect(isGridKey("a")).toBe(false);
  });
});

describe("moveFocus", () => {
  const rows = [3, 1, 2]; // Klasse A: 3 Maschinen, B: 1, C: 2

  it("Links/Rechts bewegt in der Zeile, geklemmt an den Rändern", () => {
    expect(moveFocus(rows, { row: 0, col: 0 }, "ArrowRight")).toEqual({ row: 0, col: 1 });
    expect(moveFocus(rows, { row: 0, col: 2 }, "ArrowRight")).toEqual({ row: 0, col: 2 }); // Rand
    expect(moveFocus(rows, { row: 0, col: 0 }, "ArrowLeft")).toEqual({ row: 0, col: 0 }); // Rand
  });

  it("Hoch/Runter wechselt die Zeile und klemmt die Spalte auf die Zielzeilenlänge", () => {
    // von Klasse A, Spalte 2 nach unten → Klasse B hat nur 1 Spalte → col 0
    expect(moveFocus(rows, { row: 0, col: 2 }, "ArrowDown")).toEqual({ row: 1, col: 0 });
    // von B (row 1) nach unten → C hat 2 Spalten, col bleibt 0
    expect(moveFocus(rows, { row: 1, col: 0 }, "ArrowDown")).toEqual({ row: 2, col: 0 });
    // ganz oben → bleibt
    expect(moveFocus(rows, { row: 0, col: 1 }, "ArrowUp")).toEqual({ row: 0, col: 1 });
  });

  it("Pos1/Ende springen an Zeilenanfang/-rand", () => {
    expect(moveFocus(rows, { row: 0, col: 1 }, "Home")).toEqual({ row: 0, col: 0 });
    expect(moveFocus(rows, { row: 0, col: 0 }, "End")).toEqual({ row: 0, col: 2 });
  });

  it("leeres Raster → Position unverändert", () => {
    expect(moveFocus([], { row: 0, col: 0 }, "ArrowRight")).toEqual({ row: 0, col: 0 });
  });
});
