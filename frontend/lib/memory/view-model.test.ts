// ============================================================
//  FOREMAN Frontend — lib/memory/view-model.test.ts
//  Zweck: Zusammenführung der F-SEM-Antwort — Reihenfolge=Relevanz, Autor maskiert,
//         Auflösung graceful null (nicht erfunden), Quelltyp note, Verdichtung/
//         Verknüpfung abgeleitet.
// ============================================================
import { describe, expect, it } from "vitest";
import { assembleSearchResult } from "./view-model";
import { makeNote } from "./testing/fixtures";

describe("assembleSearchResult", () => {
  it("bewahrt die Backend-Reihenfolge als Rang (Relevanz-Signal)", () => {
    const notes = [makeNote({ id: 10 }), makeNote({ id: 20 }), makeNote({ id: 30 })];
    const result = assembleSearchResult(notes, "Lager heiß");
    expect(result.hits.map((h) => h.id)).toEqual([10, 20, 30]);
    expect(result.hits.map((h) => h.rank)).toEqual([0, 1, 2]);
    expect(result.total).toBe(3);
    expect(result.query).toBe("Lager heiß");
  });

  it("maskiert den Autor zu #hex6 — niemals das rohe HMAC-Token", () => {
    const token = "v1:a3f9d8e2c1b40000000000000000000000000000000000000000000000000000";
    const result = assembleSearchResult([makeNote({ author: token })], "x");
    expect(result.hits[0]?.authorHandle).toBe("#a3f9d8");
    expect(result.hits[0]?.authorHandle).not.toContain(token);
    expect(result.hits[0]?.authorHandle).not.toContain("v1:");
  });

  it("die Auflösung bleibt null (Backend führt kein Auflösungsfeld) — nicht erfunden", () => {
    const result = assembleSearchResult([makeNote({ classification: "irgendwas" })], "x");
    expect(result.hits[0]?.resolution).toBeNull();
  });

  it("jeder Treffer ist eine Schichtnotiz (einziger realer Quelltyp)", () => {
    const result = assembleSearchResult([makeNote()], "x");
    expect(result.hits[0]?.source).toBe("note");
  });

  it("leitet Verdichtung und Verknüpfung aus realen Feldern ab", () => {
    const notes = [
      makeNote({ id: 1, machine_id: 7, shift: "Früh" }),
      makeNote({ id: 2, machine_id: 7, shift: "Spät" }),
      makeNote({ id: 3, machine_id: 9, shift: "Früh" }),
    ];
    const result = assembleSearchResult(notes, "x");
    expect(result.clusters).toHaveLength(1);
    expect(result.clusters[0]?.machineId).toBe(7);
    const types = result.relations.map((r) => r.type).sort();
    expect(types).toContain("same_machine");
    expect(types).toContain("same_shift");
  });
});
