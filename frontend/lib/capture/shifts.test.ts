// ============================================================
//  FOREMAN Frontend — lib/capture/shifts.test.ts
//  Zweck: Der gesendete Schicht-WERT muss der sein, den der Bestand führt.
//  ANLASS: `shifts.ts` war das einzige Modul in `lib/capture/` ohne Test — und
//         genau dort lief der Wert auseinander. Die Oberfläche sendete
//         `Frühschicht`, während Adapter-Weg, Szenario-Konfiguration und
//         Bestandsdaten `frueh` führen. Sichtbar wurde nichts: Die Notiz wird
//         gespeichert, das Chip zeigt sein Label, und erst eine Gruppierung über
//         die Schicht zerfällt in zwei Hälften. Für drei Schichten wären sechs
//         Bezeichner im Gedächtnis gestanden.
//  Warum ein Test und nicht nur ein Kommentar: Ein Kommentar hält den Wert nicht.
//         Diese Datei fordert ihn ein.
// ============================================================
import { describe, expect, it } from "vitest";
import { SHIFTS, SHIFT_MAX_LENGTH } from "./shifts";

// Die Schreibweise des BESTANDS, nicht die der Oberfläche. Bewusst als Literale
// hier hingeschrieben statt importiert: Der Test soll anschlagen, wenn jemand
// `shifts.ts` ändert — nicht mit ihm mitwandern.
const BESTANDS_SCHREIBWEISE = ["frueh", "spaet", "nacht"];

describe("SHIFTS", () => {
  it("sendet die Schreibweise, die der Bestand führt", () => {
    expect(SHIFTS.map((s) => s.value)).toEqual(BESTANDS_SCHREIBWEISE);
  });

  it("hält Wert und Label getrennt — die Halle darf umbenannt werden", () => {
    // AUFBAU-KONTROLLE: Wären Wert und Label dasselbe, würde eine Umbenennung
    // des Chips still den Bestand spalten. Genau so ist es entstanden.
    for (const option of SHIFTS) {
      expect(option.label).not.toBe(option.value);
      expect(option.label.length).toBeGreaterThan(0);
    }
  });

  it("bleibt unter der Längengrenze des Backends", () => {
    for (const option of SHIFTS) {
      expect(option.value.length).toBeLessThanOrEqual(SHIFT_MAX_LENGTH);
    }
  });

  it("führt jede Schicht genau einmal", () => {
    expect(new Set(SHIFTS.map((s) => s.value)).size).toBe(SHIFTS.length);
  });
});
