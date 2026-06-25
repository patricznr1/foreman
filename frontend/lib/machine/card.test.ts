// ============================================================
//  FOREMAN Frontend — lib/machine/card.test.ts
//  Zweck: Reine View-State-Logik der kanonischen lebenden Maschinenkarte —
//         Wertformat (deutsch), Datenpunkt-Status → Ansicht (Hallensprache,
//         Verdikt vs. Beobachtung) und ehrliche Frische (Stale = „Stand vor X").
//         Ohne UI/Transport testbar.
// ============================================================
import { describe, expect, it } from "vitest";

import { cardFreshness, dataPointStatusView, formatDataPointValue } from "./card";

describe("formatDataPointValue", () => {
  it("formatiert mit deutschem Dezimalkomma", () => {
    expect(formatDataPointValue(26.2)).toBe("26,2");
  });

  it("zeigt ganze Zahlen ohne Nachkomma", () => {
    expect(formatDataPointValue(212)).toBe("212");
  });

  it("zeigt einen Gedankenstrich, wenn kein Wert vorliegt", () => {
    expect(formatDataPointValue(null)).toBe("—");
  });
});

describe("dataPointStatusView", () => {
  it("Drift-Alarm ist ein Verdikt in Hallensprache (kein internes Vokabular)", () => {
    const view = dataPointStatusView("drift_alarm");
    expect(view.tone).toBe("alarm");
    expect(view.label).toBe("Abweichung erkannt");
  });

  it("offener Alarm ist ein Verdikt", () => {
    expect(dataPointStatusView("alarm").tone).toBe("alarm");
  });

  it("außerhalb des Eigenprofil-Korridors ist eine Beobachtung, kein Alarm", () => {
    const view = dataPointStatusView("out_of_band");
    expect(view.tone).toBe("observation");
    expect(view.label).toBe("Außerhalb Normalbereich");
  });

  it("außerhalb der Spezifikation ist eine Beobachtung", () => {
    const view = dataPointStatusView("out_of_spec");
    expect(view.tone).toBe("observation");
    expect(view.label).toBe("Außerhalb Spezifikation");
  });

  it("ok ist ruhig (Normalbetrieb)", () => {
    expect(dataPointStatusView("ok").tone).toBe("ok");
  });

  it("unbekannt bleibt unbekannt (nie grün geraten)", () => {
    expect(dataPointStatusView("unknown").tone).toBe("unknown");
  });
});

describe("cardFreshness", () => {
  const NOW = 1_700_000_000_000;

  it("ist live, solange der Eingangs-Stream tickt", () => {
    const fresh = cardFreshness(true, NOW - 5_000, NOW);
    expect(fresh.live).toBe(true);
    expect(fresh.standText).toBeNull();
  });

  it("zeigt bei Stream-Stopp den Stand statt frisch zu tun", () => {
    const fresh = cardFreshness(false, NOW - 3 * 60_000, NOW);
    expect(fresh.live).toBe(false);
    expect(fresh.standText).toBe("Stand vor 3 Min");
  });

  it("nennt Stunden, wenn der Stand älter ist", () => {
    const fresh = cardFreshness(false, NOW - 2 * 3_600_000, NOW);
    expect(fresh.standText).toBe("Stand vor 2 Std");
  });

  it("ohne je einen Wert kein Stand (ehrlich leer)", () => {
    const fresh = cardFreshness(false, null, NOW);
    expect(fresh.live).toBe(false);
    expect(fresh.standText).toBeNull();
  });

  it("ein ungültiger Zeitstempel (NaN) zeigt keinen Stand statt 'vor NaN'", () => {
    // Date.parse eines korrupten last_reading_at liefert NaN — defensiv zu „kein
    // Stand" degradiert, nie ein „vor NaN Tagen" ins UI.
    const fresh = cardFreshness(false, Number.NaN, NOW);
    expect(fresh.live).toBe(false);
    expect(fresh.standText).toBeNull();
  });
});
