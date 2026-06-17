// ============================================================
//  FOREMAN Frontend — lib/memory/time.test.ts
//  Zweck: Relative Zeitangabe in Hallensprache, mit injiziertem jetzt (deterministisch).
// ============================================================
import { describe, expect, it } from "vitest";
import { relativeTime } from "./time";

const NOW = new Date("2026-06-17T12:00:00+00:00");

describe("relativeTime", () => {
  it("ungültiger Stempel ergibt unbekannt", () => {
    expect(relativeTime("kein-datum", NOW)).toBe("unbekannt");
  });

  it("Minuten, Stunden, gestern, Wochen", () => {
    expect(relativeTime("2026-06-17T11:30:00+00:00", NOW)).toBe("vor 30 Minuten");
    expect(relativeTime("2026-06-17T09:00:00+00:00", NOW)).toBe("vor 3 Stunden");
    expect(relativeTime("2026-06-16T09:00:00+00:00", NOW)).toBe("gestern");
    expect(relativeTime("2026-05-27T12:00:00+00:00", NOW)).toBe("vor 3 Wochen");
  });

  it("Zukunft wird zu soeben (keine negative Angabe)", () => {
    expect(relativeTime("2026-06-18T12:00:00+00:00", NOW)).toBe("soeben");
  });
});
