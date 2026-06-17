// ============================================================
//  FOREMAN Frontend — lib/capture/types.ts
//  Zweck: Die View-State-Typen der Erfassung (Sektion J). Transport-agnostisch,
//         gegen den REALEN worker_notes-Vertrag (contracts.ts:WorkerNoteCreate).
//         Eine Notiz erfassen ist eine menschliche Daten-Eingabe — keine Aktorik.
//  Architektur-Einordnung: Erfassungs-Logik (Schicht 2). Reine Typen.
// ============================================================
import type { WorkerNoteCreate, WorkerNoteRead } from "@/lib/api/contracts";

/**
 * Die drei Werker-Kategorien einer Beobachtung. Reine FRONTEND-Konvention: das
 * Backend erzwingt keine Werteliste (DB-Spalte ist Freitext, §5). Mehrkanalig
 * (Farbe + Symbol + Label) kodiert in lib/capture/classification.ts. Die Kategorie
 * wählt der Werker MANUELL — es gibt keinen automatischen Klassifikations-Vorschlag
 * ([VISION], bewusst nicht erfunden).
 */
export type Classification = "routine" | "auffaellig" | "kritisch";

/**
 * Was der Werker im Formular erfasst, bevor es zum POST-Body wird (submit.ts).
 * `text` ist der einzige Pflichtteil; Zuordnung (Maschine/Schicht) ist durch
 * Kontext-Vorbelegung minimiert, Kategorie optional (Studie §4J).
 */
export interface CaptureDraft {
  text: string;
  machineId: number | null;
  shift: string | null;
  classification: Classification | null;
}

/**
 * Eine lokal gepufferte, noch nicht gesendete Notiz (Offline-Queue, outbox.ts).
 * DATENSCHUTZ: hält den vom Werker eingegebenen Klartext NUR bis zum erfolgreichen
 * Senden — danach wird das Item aus der Queue gelöscht (kein dauerhafter
 * Klartext-PII-Cache, der die serverseitige Maskierung umginge, §8).
 */
export interface QueuedNote {
  localId: string;
  payload: WorkerNoteCreate;
  enqueuedAt: string; // ISO 8601 (lokal gestempelt, nur informativ)
}

/**
 * Ergebnis eines einzelnen Sendeversuchs. `forbidden`/`unauthorized`/`validation`
 * sind HARTE Grenzen (nicht durch Retry behebbar → aus der Queue nehmen); `error`
 * ist transient (5xx/Netz → in der Queue belassen, erneut versuchen). Spiegelt das
 * Reason-Schema aus lib/alarms/use-acknowledge.ts.
 */
export type SubmitOutcome =
  | { ok: true; note: WorkerNoteRead }
  | {
      ok: false;
      reason: "validation" | "unauthorized" | "forbidden" | "error";
      status?: number;
    };

/** Ob ein Sende-Fehlschlag transient ist (erneut versuchen) oder hart (verwerfen). */
export function isTransientFailure(outcome: SubmitOutcome): boolean {
  return !outcome.ok && outcome.reason === "error";
}

/** Sichtbarer Sync-Zustand der Erfassung (Sync-Status-Anzeige, Studie §4J). */
export type SyncState =
  | { kind: "idle" } // nichts ausstehend, bereit
  | { kind: "sending" } // wird gerade gesendet
  | { kind: "synced"; at: string } // zuletzt erfolgreich gesendet
  | { kind: "queued"; pending: number } // lokal gepuffert, wartet auf Netz
  | { kind: "error"; pending: number }; // letzter Flush schlug fehl, bleibt gepuffert
