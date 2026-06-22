// ============================================================
//  FOREMAN Frontend — lib/event-chains/symbols.test.ts
//  Zweck: event_type → formcodiertes Symbol + Hidden-Term-Wording (Abweichung statt Drift).
// ============================================================
import { describe, expect, it } from "vitest";
import { SYMBOL_LABEL, eventTypeLabel, symbolFor } from "./symbols";

describe("symbolFor — event_type → Form", () => {
  it("bildet jeden Typ auf die richtige Symbolklasse", () => {
    expect(symbolFor("anchor_alarm")).toBe("anchor");
    expect(symbolFor("drift_alarm")).toBe("drift");
    expect(symbolFor("prior_alarm")).toBe("alarm");
    expect(symbolFor("worker_note")).toBe("note");
    expect(symbolFor("maintenance")).toBe("maintenance");
  });
});

describe("eventTypeLabel — Hidden-Term: Abweichung statt Drift", () => {
  it("nennt drift_alarm 'Abweichungs-Alarm', nicht 'Drift'", () => {
    expect(eventTypeLabel("drift_alarm")).toBe("Abweichungs-Alarm");
    expect(eventTypeLabel("drift_alarm").toLowerCase()).not.toContain("drift");
  });

  it("labelt die übrigen Typen in Hallensprache", () => {
    expect(eventTypeLabel("anchor_alarm")).toBe("Anker-Alarm");
    expect(eventTypeLabel("worker_note")).toBe("Werkernotiz");
    expect(eventTypeLabel("maintenance")).toBe("Wartung");
  });
});

describe("SYMBOL_LABEL", () => {
  it("hat ein Label je Form (Abweichung, nicht Drift)", () => {
    expect(SYMBOL_LABEL.drift).toBe("Abweichung");
    expect(SYMBOL_LABEL.anchor).toBe("Anker");
  });
});
