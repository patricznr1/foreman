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

  it("kürzt langen Text an der Wortgrenze mit Auslassung (kein Mittenschnitt)", () => {
    const long =
      "Lagerwechsel Spindellagerschaden Schichtuebergabe Vibrationsmuster Temperaturanstieg Nachlauf";
    const out = toExcerpt(long, 30);
    expect(out.endsWith("…")).toBe(true);
    // Der behaltene Rumpf (ohne Auslassung) muss ein Präfix des Originals sein …
    const body = out.replace(/\s*…$/, "");
    expect(long.startsWith(body)).toBe(true);
    // … und genau an einer Wortgrenze enden (nächstes Zeichen ist Ende oder Leerzeichen).
    const nextChar = long.charAt(body.length);
    expect(nextChar === "" || nextChar === " ").toBe(true);
    expect(out.length).toBeLessThanOrEqual(32);
  });

  it("erhält Maskierungs-Marker wie [PERSON] (entmaskiert nichts)", () => {
    expect(toExcerpt("Übergabe an [PERSON] notiert")).toContain("[PERSON]");
  });
});
