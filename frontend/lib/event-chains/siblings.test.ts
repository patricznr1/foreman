// ============================================================
//  FOREMAN Frontend — lib/event-chains/siblings.test.ts
//  Zweck: Geschwister-Mapping — navigierbar NUR mit realer Ziel-Erklärung; leere
//         Eingabe → leere Ausgabe (kein Fake); ehrliche Labels.
// ============================================================
import { describe, expect, it } from "vitest";
import { siblingLabel, toSiblingModels } from "./siblings";
import { makeSibling } from "./testing/fixtures";

describe("toSiblingModels — Geschwister-Mapping", () => {
  it("navigierbar nur mit realer Ziel-Erklärung", () => {
    const models = toSiblingModels([
      makeSibling({ explanation_id: 5, machine_id: 9, machine_class: "cnc" }),
      makeSibling(),
    ]);
    expect(models[0]?.navigable).toBe(true);
    expect(models[0]?.explanationId).toBe(5);
    expect(models[1]?.navigable).toBe(false);
    expect(models[1]?.machineId).toBeNull();
    expect(models[1]?.explanationId).toBeNull();
  });

  it("leere Eingabe → leere Ausgabe (kein Fake)", () => {
    expect(toSiblingModels([])).toEqual([]);
  });
});

describe("siblingLabel — ehrlich nach Verfügbarkeit", () => {
  it("benennt die Schwestermaschine, wenn bekannt", () => {
    const withMachine = toSiblingModels([makeSibling({ machine_id: 9, machine_class: "cnc" })])[0];
    expect(withMachine && siblingLabel(withMachine)).toContain("Schwestermaschine 9");
  });

  it("fällt ehrlich auf 'Ähnlicher Vergangenheitsfall' zurück", () => {
    const bare = toSiblingModels([makeSibling()])[0];
    expect(bare && siblingLabel(bare)).toBe("Ähnlicher Vergangenheitsfall");
  });
});
