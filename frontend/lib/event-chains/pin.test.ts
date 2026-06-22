// ============================================================
//  FOREMAN Frontend — lib/event-chains/pin.test.ts
//  Zweck: Pin-Store — pinnt je Maschine, friert den Stand ein, idempotent,
//         isPinned/unpin. Storage injiziert (kein Browser).
// ============================================================
import { describe, expect, it } from "vitest";
import { type PinStorage, type PinnedChain, isPinned, pinChain, readPinnedChains, unpinChain } from "./pin";

function makeStorage(): PinStorage {
  const map = new Map<string, string>();
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => {
      map.set(key, value);
    },
  };
}

function makePin(over: Partial<PinnedChain> = {}): PinnedChain {
  return {
    explanationId: 1,
    machineId: 7,
    anchorAlarmId: 1,
    confidence: "hoch",
    isHypothesis: false,
    eventCount: 3,
    stampedAt: "2026-06-14T12:05:00+00:00",
    pinnedAt: "2026-06-14T13:00:00+00:00",
    ...over,
  };
}

describe("pin store", () => {
  it("pinnt, liest je Maschine, friert den Stand ein", () => {
    const storage = makeStorage();
    pinChain(makePin(), storage);
    const list = readPinnedChains(7, storage);
    expect(list.length).toBe(1);
    expect(list[0]?.stampedAt).toBe("2026-06-14T12:05:00+00:00");
    expect(readPinnedChains(99, storage)).toEqual([]);
  });

  it("ist idempotent über die explanationId (überschreibt)", () => {
    const storage = makeStorage();
    pinChain(makePin(), storage);
    pinChain(makePin({ eventCount: 5 }), storage);
    const list = readPinnedChains(7, storage);
    expect(list.length).toBe(1);
    expect(list[0]?.eventCount).toBe(5);
  });

  it("isPinned + unpin", () => {
    const storage = makeStorage();
    pinChain(makePin(), storage);
    expect(isPinned(1, storage)).toBe(true);
    unpinChain(1, storage);
    expect(isPinned(1, storage)).toBe(false);
  });

  it("filtert schemafremde Einträge aus dem Storage (kein Runtime-Crash)", () => {
    const storage = makeStorage();
    // Valides Array, aber mit schemafremden/leeren Einträgen (z. B. alte Version).
    storage.setItem(
      "foreman.chains.pinned",
      JSON.stringify([makePin({ explanationId: 1 }), { explanationId: "x", pinnedAt: 42 }, null]),
    );
    const list = readPinnedChains(7, storage);
    expect(list.length).toBe(1);
    expect(list[0]?.explanationId).toBe(1);
  });
});
