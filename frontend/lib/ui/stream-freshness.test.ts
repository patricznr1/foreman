// ============================================================
//  FOREMAN Frontend — lib/ui/stream-freshness.test.ts
//  Zweck: Sichert die EHRLICHE Frische des globalen Live-Badges: „Live" NUR, wenn
//         der WS-Transport offen ist UND der Eingangs-Stream wirklich tickt — ein
//         WS-Connect über statischer Historie ist „Verlauf", kein Live (Verfassung:
//         kein Etikett ohne Strom). Konsistent mit der Topologie-Kachel.
// ============================================================
import { describe, expect, it } from "vitest";
import { streamBadgeFreshness } from "./stream-freshness";

describe("streamBadgeFreshness", () => {
  it("'live' nur, wenn WS offen UND der Eingangs-Stream tickt", () => {
    expect(streamBadgeFreshness(true, true)).toBe("live");
  });

  it("'Verlauf' (history), wenn kein Stream tickt — auch bei offener WS-Verbindung", () => {
    // Genau der Fall, den der Auftrag verbietet: kein „Live" über statischer Historie.
    expect(streamBadgeFreshness(true, false)).toBe("history");
  });

  it("'Verlauf' (history), wenn weder Stream tickt noch Verbindung steht", () => {
    expect(streamBadgeFreshness(false, false)).toBe("history");
  });

  it("'Gecacht' (cached), wenn der Stream tickt, aber die WS-Verbindung weg ist", () => {
    expect(streamBadgeFreshness(false, true)).toBe("cached");
  });
});
