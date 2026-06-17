// ============================================================
//  FOREMAN Frontend — lib/alarms/diff.test.ts
//  Zweck: Live-Insert-Diff — nur echte Neuzugänge pulsen, Erstladung pulst nichts.
// ============================================================
import { describe, expect, it } from "vitest";
import { diffNewIds, idSet } from "./diff";
import { alarm } from "./testing/fixtures";

describe("diffNewIds", () => {
  it("Erstladung (prev=null) markiert NICHTS als neu", () => {
    const next = [alarm({ id: 1 }), alarm({ id: 2 })];
    expect(diffNewIds(null, next).size).toBe(0);
  });

  it("nur IDs, die vorher fehlten, sind frisch", () => {
    const prev = new Set([1, 2]);
    const next = [alarm({ id: 1 }), alarm({ id: 2 }), alarm({ id: 3 })];
    const fresh = diffNewIds(prev, next);
    expect([...fresh]).toEqual([3]);
  });

  it("idSet bildet die ID-Menge", () => {
    expect([...idSet([alarm({ id: 5 }), alarm({ id: 9 })])].sort()).toEqual([5, 9]);
  });
});
