// ============================================================
//  FOREMAN Frontend — lib/machine/grouping.test.ts
//  Zweck: Reine Gruppierung des Karten-Grids nach Maschinenklasse → Synoptik-Stufe
//         (Fördern/Pressen/Handling/Bestücken/Endkontrolle), in der kanonischen
//         Linien-Reihenfolge; unbekannte Klassen behalten ihren rohen Namen
//         (kein erfundenes Label) und reihen sich hinten ein.
// ============================================================
import { describe, expect, it } from "vitest";

import type { MachineCardOut } from "@/lib/api/contracts";
import { makeMachineCard } from "@/lib/machine/testing/card-fixture";

import { groupByStage, stageLabel } from "./grouping";

function card(id: number, machineClass: string | null, label = `M-${id}`): MachineCardOut {
  return makeMachineCard({ id, label, machine_class: machineClass, external_id: label });
}

describe("stageLabel", () => {
  it("übersetzt bekannte Klassen in Synoptik-Stufen", () => {
    expect(stageLabel("feeder")).toBe("Fördern");
    expect(stageLabel("servo_press")).toBe("Pressen");
    expect(stageLabel("servo_axis")).toBe("Handling");
    expect(stageLabel("robot")).toBe("Bestücken");
    expect(stageLabel("vision")).toBe("Endkontrolle");
  });

  it("behält unbekannte Klassen als rohen Namen (kein erfundenes Label)", () => {
    expect(stageLabel("centrifuge")).toBe("centrifuge");
  });

  it("nennt fehlende Klasse ehrlich", () => {
    expect(stageLabel(null)).toBe("Ohne Klasse");
  });
});

describe("groupByStage", () => {
  it("gruppiert in der kanonischen Linien-Reihenfolge", () => {
    const groups = groupByStage([
      card(1, "vision"),
      card(2, "feeder"),
      card(3, "servo_press"),
      card(4, "feeder"),
    ]);
    expect(groups.map((g) => g.stage)).toEqual(["Fördern", "Pressen", "Endkontrolle"]);
    // Fördern bündelt beide Feeder, stabile Eingabe-Reihenfolge.
    expect(groups[0]?.cards.map((c) => c.id)).toEqual([2, 4]);
  });

  it("reiht unbekannte Klassen hinter die bekannten Stufen", () => {
    const groups = groupByStage([card(1, "centrifuge"), card(2, "feeder")]);
    expect(groups.map((g) => g.stage)).toEqual(["Fördern", "centrifuge"]);
  });
});
