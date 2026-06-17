// ============================================================
//  FOREMAN Frontend — lib/alarms/window.test.ts
//  Zweck: Virtualisierungs-Mathematik — nur Sichtbares + Overscan, stabile Polster.
// ============================================================
import { describe, expect, it } from "vitest";
import { windowRange } from "./window";

describe("windowRange", () => {
  it("Anfang: rendert Sichtbares + Overscan, paddingTop 0", () => {
    const r = windowRange({ scrollTop: 0, viewportHeight: 400, rowHeight: 72, count: 1000 });
    expect(r.startIndex).toBe(0);
    expect(r.paddingTop).toBe(0);
    // 400/72 ≈ 6 sichtbar + 4 overscan
    expect(r.endIndex).toBeGreaterThanOrEqual(6);
    expect(r.endIndex).toBeLessThan(1000);
    expect(r.totalHeight).toBe(72_000);
  });

  it("Mitte: Fenster wandert, Polster halten die Geometrie (kein Sprung)", () => {
    const r = windowRange({
      scrollTop: 7200,
      viewportHeight: 400,
      rowHeight: 72,
      count: 1000,
      overscan: 4,
    });
    expect(r.startIndex).toBe(100 - 4); // 7200/72 = 100, minus overscan
    expect(r.paddingTop).toBe(r.startIndex * 72);
    expect(r.paddingTop + (r.endIndex - r.startIndex) * 72 + r.paddingBottom).toBe(r.totalHeight);
  });

  it("nur Sichtbares im DOM: Fensterbreite ≪ count bei großer Liste", () => {
    const r = windowRange({ scrollTop: 0, viewportHeight: 400, rowHeight: 72, count: 10_000 });
    expect(r.endIndex - r.startIndex).toBeLessThan(20);
  });

  it("leere/degenerierte Eingaben → leeres Fenster", () => {
    expect(windowRange({ scrollTop: 0, viewportHeight: 400, rowHeight: 72, count: 0 }).endIndex).toBe(
      0,
    );
    expect(
      windowRange({ scrollTop: 0, viewportHeight: 0, rowHeight: 72, count: 10 }).endIndex,
    ).toBe(0);
  });

  it("Überscrollen wird geklemmt (kein negatives Polster)", () => {
    const r = windowRange({ scrollTop: 999_999, viewportHeight: 400, rowHeight: 72, count: 50 });
    expect(r.endIndex).toBe(50);
    expect(r.paddingBottom).toBe(0);
    expect(r.paddingTop).toBeGreaterThanOrEqual(0);
  });
});
