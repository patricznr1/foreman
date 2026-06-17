// ============================================================
//  FOREMAN Frontend — lib/capture/sync.ts
//  Zweck: Den sichtbaren Sync-Status ableiten und in Hallensprache benennen
//         (Studie §4J: „gespeichert · synchronisiert" / „gespeichert · wartet auf
//         Netz"). WICHTIG: „wartet auf Netz" ist NORMAL, kein Alarm — kein
//         Alarm-Rot, ein ruhiges Symbol (die Farb-Zuordnung trifft die Komponente).
//  Architektur-Einordnung: Erfassungs-Logik (Schicht 2). Reine Logik, testbar.
// ============================================================
import type { SyncState } from "./types";

/** Leitet den Sync-Zustand aus den Hook-Signalen ab (rein). */
export function deriveSyncState(input: {
  sending: boolean;
  flushing: boolean;
  pending: number;
  hadError: boolean;
  lastSyncedAt: string | null;
}): SyncState {
  if (input.sending || input.flushing) {
    return { kind: "sending" };
  }
  if (input.pending > 0) {
    return input.hadError
      ? { kind: "error", pending: input.pending }
      : { kind: "queued", pending: input.pending };
  }
  if (input.lastSyncedAt) {
    return { kind: "synced", at: input.lastSyncedAt };
  }
  return { kind: "idle" };
}

/** Kurzer Status-Text in Hallensprache; leer im Ruhezustand. */
export function syncStatusText(state: SyncState): string {
  switch (state.kind) {
    case "idle":
      return "";
    case "sending":
      return "wird gesendet …";
    case "synced":
      return "gespeichert · synchronisiert";
    case "queued":
    case "error":
      // Beide Fälle sind „normal" (transient): die Notiz ist lokal sicher und wird
      // gesendet, sobald wieder Netz da ist. Kein Alarm-Wording, kein Rot.
      return state.pending > 1
        ? `${state.pending} Notizen gespeichert · werden gesendet, sobald online`
        : "gespeichert · wird gesendet, sobald online";
  }
}
