// ============================================================
//  FOREMAN Frontend — lib/memory/relations.test.ts
//  Zweck: Verknüpfung nur aus realen Feldern (gleiche Maschine/Schicht/Woche);
//         nichts erfunden; bei lauter verschiedenen Treffern keine Beziehung.
// ============================================================
import { describe, expect, it } from "vitest";
import { RELATION_LABEL, deriveRelations } from "./relations";
import { assembleSearchResult } from "./view-model";
import { makeNote } from "./testing/fixtures";

function hitsFrom(notes: Parameters<typeof assembleSearchResult>[0]) {
  return assembleSearchResult(notes, "x").hits;
}

describe("deriveRelations", () => {
  it("erkennt gleiche Maschine, gleiche Schicht und zeitliche Nähe", () => {
    const hits = hitsFrom([
      makeNote({ id: 1, machine_id: 7, shift: "Früh", created_at: "2026-06-10T08:00:00+00:00" }),
      makeNote({ id: 2, machine_id: 7, shift: "Früh", created_at: "2026-06-11T08:00:00+00:00" }),
    ]);
    const types = deriveRelations(hits).map((r) => r.type).sort();
    expect(types).toEqual(["same_machine", "same_shift", "temporal"]);
  });

  it("erfindet keine Beziehung, wenn alles verschieden ist", () => {
    const hits = hitsFrom([
      makeNote({ id: 1, machine_id: 7, shift: "Früh", created_at: "2026-01-01T08:00:00+00:00" }),
      makeNote({ id: 2, machine_id: 9, shift: "Spät", created_at: "2026-06-11T08:00:00+00:00" }),
    ]);
    expect(deriveRelations(hits)).toHaveLength(0);
  });

  it("die Begründung ist faktisch (nennt Anzahl + reales Feld)", () => {
    const hits = hitsFrom([
      makeNote({ id: 1, machine_id: 7 }),
      makeNote({ id: 2, machine_id: 7 }),
    ]);
    const machine = deriveRelations(hits).find((r) => r.type === "same_machine");
    expect(machine?.reason).toContain("Maschine 7");
    expect(machine?.hitIds).toEqual([1, 2]);
  });

  it("hat ein farbunabhängiges Label je Beziehungstyp", () => {
    expect(RELATION_LABEL.same_machine).toBe("Gleiche Maschine");
    expect(RELATION_LABEL.same_shift).toBe("Gleiche Schicht");
    expect(RELATION_LABEL.temporal).toBe("Zeitliche Nähe");
  });
});
