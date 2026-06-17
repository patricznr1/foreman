// ============================================================
//  FOREMAN Frontend — lib/memory/excerpt.test.ts
//  Zweck: Auszug — Wortgrenze, Whitespace, Maskierungs-Marker bleiben erhalten.
// ============================================================
import { describe, expect, it } from "vitest";
import { toExcerpt } from "./excerpt";

describe("toExcerpt", () => {
  it("lässt kurzen Text unverändert (nur Whitespace normalisiert)", () => {
    expect(toExcerpt("Lager   heiß")).toBe("Lager heiß");
  });

  it("kürzt langen Text an der Wortgrenze mit Auslassung", () => {
    const long = "Wort ".repeat(80).trim();
    const out = toExcerpt(long, 40);
    expect(out.length).toBeLessThanOrEqual(42);
    expect(out.endsWith("…")).toBe(true);
    expect(out).not.toMatch(/Wor$/); // nicht mitten im Wort abgeschnitten
  });

  it("erhält Maskierungs-Marker wie [PERSON] (entmaskiert nichts)", () => {
    expect(toExcerpt("Übergabe an [PERSON] notiert")).toContain("[PERSON]");
  });
});
