// ============================================================
//  FOREMAN Frontend — lib/capture/sync.test.ts
//  Zweck: Sichert die Sync-Status-Ableitung und das Hallensprache-Wording.
// ============================================================
import { describe, expect, it } from "vitest";
import { deriveSyncState, syncStatusText } from "./sync";

const base = { sending: false, flushing: false, pending: 0, hadError: false, lastSyncedAt: null };

describe("deriveSyncState", () => {
  it("zeigt 'sending' während Senden ODER Flush", () => {
    expect(deriveSyncState({ ...base, sending: true }).kind).toBe("sending");
    expect(deriveSyncState({ ...base, flushing: true }).kind).toBe("sending");
  });

  it("zeigt 'queued' bei ausstehenden Notizen ohne Fehler", () => {
    expect(deriveSyncState({ ...base, pending: 2 })).toEqual({ kind: "queued", pending: 2 });
  });

  it("zeigt 'error' bei ausstehenden Notizen nach transientem Flush-Fehler", () => {
    expect(deriveSyncState({ ...base, pending: 1, hadError: true })).toEqual({
      kind: "error",
      pending: 1,
    });
  });

  it("zeigt 'synced' wenn nichts aussteht und schon einmal gesendet wurde", () => {
    expect(deriveSyncState({ ...base, lastSyncedAt: "2026-06-17T15:00:00+00:00" })).toEqual({
      kind: "synced",
      at: "2026-06-17T15:00:00+00:00",
    });
  });

  it("ist sonst 'idle' (frisch, nichts ausstehend)", () => {
    expect(deriveSyncState(base)).toEqual({ kind: "idle" });
  });
});

describe("syncStatusText", () => {
  it("benennt den Puffer in Hallensprache OHNE Alarm-Wording", () => {
    expect(syncStatusText({ kind: "queued", pending: 1 })).toBe(
      "gespeichert · wird gesendet, sobald online",
    );
    expect(syncStatusText({ kind: "queued", pending: 3 })).toContain("3 Notizen");
    // Auch der transiente Fehlerfall bleibt neutral (kein „Fehler"/kein Alarm).
    const errorText = syncStatusText({ kind: "error", pending: 2 });
    expect(errorText.toLowerCase()).not.toContain("fehler");
    expect(errorText.toLowerCase()).not.toContain("alarm");
  });

  it("meldet erfolgreiche Synchronisation und Ruhe", () => {
    expect(syncStatusText({ kind: "synced", at: "x" })).toBe("gespeichert · synchronisiert");
    expect(syncStatusText({ kind: "idle" })).toBe("");
  });
});
