// ============================================================
//  FOREMAN Frontend — lib/alarms/priority.test.ts
//  Zweck: ISA-18.2-Staffelung — Severity→Tier, Feinrang, max. eine Rot-Stufe.
// ============================================================
import { describe, expect, it } from "vitest";
import {
  PRIORITY_ORDER,
  PRIORITY_TOKEN,
  priorityRank,
  severityRank,
  severityToPriority,
} from "./priority";

describe("severityToPriority — 5 Backend-Severities → ISA-Tiers", () => {
  it("emergency und critical fallen in den EINEN Rot-Tier (kritisch)", () => {
    expect(severityToPriority("emergency")).toBe("critical");
    expect(severityToPriority("critical")).toBe("critical");
  });

  it("alarm→hoch, warning→mittel, info→niedrig", () => {
    expect(severityToPriority("alarm")).toBe("high");
    expect(severityToPriority("warning")).toBe("medium");
    expect(severityToPriority("info")).toBe("low");
  });

  it("unbekannte Severity → Journal (neutral, kein Farbgewicht)", () => {
    expect(severityToPriority("bogus")).toBe("journal");
    expect(severityToPriority("")).toBe("journal");
  });

  it("reservierte Schlüssel lösen NICHT über die Prototypkette auf (Journal/Fallback)", () => {
    expect(severityToPriority("__proto__")).toBe("journal");
    expect(severityToPriority("constructor")).toBe("journal");
    expect(severityToPriority("hasOwnProperty")).toBe("journal");
    expect(severityRank("constructor")).toBe(5);
    expect(severityRank("toString")).toBe(5);
  });
});

describe("Rang & Tokens", () => {
  it("kritisch hat den höchsten Rang (0), Journal den niedrigsten", () => {
    expect(priorityRank("critical")).toBe(0);
    expect(priorityRank("journal")).toBe(PRIORITY_ORDER.length - 1);
  });

  it("Feinrang hält Notfall vor Kritisch innerhalb des Rot-Tiers", () => {
    expect(severityRank("emergency")).toBeLessThan(severityRank("critical"));
  });

  it("nur kritisch nutzt das vollflächige Rot-Token", () => {
    expect(PRIORITY_TOKEN.critical).toBe("alarm-critical");
    expect(PRIORITY_TOKEN.high).toBe("alarm-high");
    expect(PRIORITY_TOKEN.journal).toBe("alarm-journal");
  });
});
