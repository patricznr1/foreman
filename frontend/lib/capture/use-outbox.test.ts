// ============================================================
//  FOREMAN Frontend — lib/capture/use-outbox.test.ts
//  Zweck: Sichert die §8-Kern-Invariante des Flush: Erfolg ODER harter Fehler →
//         Item entfernt (Lösch-nach-Senden); transienter Fehler → Item BLEIBT
//         gepuffert (späterer Retry). Plus Netz-Übergang löst den Flush aus.
// ============================================================
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { enqueueNote, readOutbox } from "./outbox";
import { useOutbox } from "./use-outbox";

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

function stubStatus(status: number) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ status, json: async () => ({}) }) as Response),
  );
}

function seed(text: string, id: string) {
  enqueueNote({ text }, { storage: window.localStorage, makeId: () => id, now: () => "t" });
}

describe("useOutbox — Flush (Lösch-nach-Senden, §8)", () => {
  it("Erfolg (201): entfernt das gesendete Item — kein Klartext bleibt", async () => {
    seed("erste", "a");
    seed("zweite", "b");
    stubStatus(201);
    const { result } = renderHook(() => useOutbox(false)); // offline: kein Auto-Flush beim Mount
    await act(async () => {
      await result.current.flush();
    });
    expect(readOutbox(window.localStorage)).toHaveLength(0);
    expect(result.current.pending).toBe(0);
    expect(result.current.hadError).toBe(false);
  });

  it("transienter Fehler (503): behält das Item gepuffert + meldet hadError", async () => {
    seed("bleibt", "a");
    stubStatus(503);
    const { result } = renderHook(() => useOutbox(false));
    await act(async () => {
      await result.current.flush();
    });
    expect(readOutbox(window.localStorage)).toHaveLength(1);
    expect(result.current.pending).toBe(1);
    expect(result.current.hadError).toBe(true);
  });

  it("harter Fehler (403): entfernt das Item (kein endloses Liegenbleiben)", async () => {
    seed("verworfen", "a");
    stubStatus(403);
    const { result } = renderHook(() => useOutbox(false));
    await act(async () => {
      await result.current.flush();
    });
    expect(readOutbox(window.localStorage)).toHaveLength(0);
    expect(result.current.hadError).toBe(false);
  });

  it("Netz-Rückkehr (online=true beim Mount) flusht automatisch", async () => {
    seed("auto", "a");
    stubStatus(201);
    renderHook(() => useOutbox(true));
    await waitFor(() => expect(readOutbox(window.localStorage)).toHaveLength(0));
  });
});
