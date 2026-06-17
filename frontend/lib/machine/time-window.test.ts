// ============================================================
//  FOREMAN Frontend — lib/machine/time-window.test.ts
//  Zweck: Sichert die Zeitfenster (Schicht/Tag/Woche) innerhalb der Backend-Grenze.
// ============================================================
import { describe, expect, it } from "vitest";

import {
  DEFAULT_TIME_WINDOW,
  MAX_BACKEND_HOURS,
  TIME_WINDOWS,
  timeWindow,
  windowStartMs,
} from "./time-window";

describe("TIME_WINDOWS", () => {
  it("bietet Schicht/Tag/Woche, alle innerhalb der Backend-Obergrenze (168h)", () => {
    expect(TIME_WINDOWS.map((w) => w.id)).toEqual(["shift", "day", "week"]);
    for (const w of TIME_WINDOWS) {
      expect(w.hours).toBeLessThanOrEqual(MAX_BACKEND_HOURS);
    }
    expect(TIME_WINDOWS.find((w) => w.id === "week")?.hours).toBe(168);
  });

  it("timeWindow löst eine ID zu Label + Stunden auf", () => {
    expect(timeWindow("day").hours).toBe(24);
    expect(timeWindow("day").label).toBe("Tag");
  });

  it("windowStartMs zieht die Stunden von now ab", () => {
    const now = Date.parse("2026-06-17T12:00:00Z");
    expect(windowStartMs(now, 24)).toBe(now - 24 * 3600 * 1000);
  });

  it("Default-Fenster ist Tag", () => {
    expect(DEFAULT_TIME_WINDOW).toBe("day");
  });
});
