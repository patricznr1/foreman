// ============================================================
//  FOREMAN Frontend — lib/memory/cluster.test.ts
//  Zweck: Verdichtung über gleiche Maschine; Einzeltreffer ist kein Muster;
//         Auflösungs-Bezug graceful null (nicht erfunden).
// ============================================================
import { describe, expect, it } from "vitest";
import { clusterByMachine } from "./cluster";
import { assembleSearchResult } from "./view-model";
import { makeNote } from "./testing/fixtures";

function hitsFrom(notes: Parameters<typeof assembleSearchResult>[0]) {
  return assembleSearchResult(notes, "x").hits;
}

describe("clusterByMachine", () => {
  it("gruppiert >= 2 Treffer derselben Maschine zu einem Cluster", () => {
    const hits = hitsFrom([
      makeNote({ id: 1, machine_id: 7 }),
      makeNote({ id: 2, machine_id: 7 }),
    ]);
    const clusters = clusterByMachine(hits);
    expect(clusters).toHaveLength(1);
    expect(clusters[0]?.hits).toHaveLength(2);
    expect(clusters[0]?.sharedResolution).toBeNull();
  });

  it("ein Einzeltreffer an einer Maschine ist kein Cluster", () => {
    const hits = hitsFrom([makeNote({ id: 1, machine_id: 7 }), makeNote({ id: 2, machine_id: 9 })]);
    expect(clusterByMachine(hits)).toHaveLength(0);
  });

  it("ignoriert Treffer ohne Maschine (machine_id null)", () => {
    const hits = hitsFrom([
      makeNote({ id: 1, machine_id: null }),
      makeNote({ id: 2, machine_id: null }),
    ]);
    expect(clusterByMachine(hits)).toHaveLength(0);
  });

  it("sortiert größere Verdichtung zuerst", () => {
    const hits = hitsFrom([
      makeNote({ id: 1, machine_id: 7 }),
      makeNote({ id: 2, machine_id: 9 }),
      makeNote({ id: 3, machine_id: 9 }),
      makeNote({ id: 4, machine_id: 9 }),
      makeNote({ id: 5, machine_id: 7 }),
    ]);
    const clusters = clusterByMachine(hits);
    expect(clusters[0]?.machineId).toBe(9);
    expect(clusters[0]?.hits).toHaveLength(3);
  });
});
