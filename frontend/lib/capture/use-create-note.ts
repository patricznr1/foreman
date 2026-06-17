// ============================================================
//  FOREMAN Frontend — lib/capture/use-create-note.ts
//  Zweck: Eine Notiz erfassen (HITL-Daten-Eingabe, keine Aktorik). Online →
//         POST über den BFF; offline ODER transienter Fehler → lokal puffern
//         (wird gesendet, sobald online); harte Fehler (Validierung/Auth) → melden.
//         Spiegelt das Action-Hook-Muster aus lib/alarms/use-acknowledge.ts.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useState } from "react";
import type { WorkerNoteRead } from "@/lib/api/contracts";
import { enqueueNote } from "./outbox";
import { buildNotePayload, submitNote } from "./submit";
import type { CaptureDraft, QueuedNote } from "./types";

export type CaptureSubmitResult =
  | { kind: "sent"; note: WorkerNoteRead }
  | { kind: "queued"; item: QueuedNote }
  // Harte, nicht durch Retry behebbare Grenzen — der Werker erfährt den Grund.
  | { kind: "error"; reason: "validation" | "unauthorized" | "forbidden"; status?: number };

export interface UseCreateNoteResult {
  submit: (draft: CaptureDraft) => Promise<CaptureSubmitResult>;
  sending: boolean;
}

/**
 * `author` = eigene user_id (Klartext; serverseitig zu HMAC pseudonymisiert, §8).
 * `online` wird hineingereicht (useOnline) — so bleibt der Hook ohne Netz testbar.
 */
export function useCreateNote(author: string | null, online: boolean): UseCreateNoteResult {
  const [sending, setSending] = useState(false);

  const submit = useCallback(
    async (draft: CaptureDraft): Promise<CaptureSubmitResult> => {
      const payload = buildNotePayload(draft, author);
      // Offline → sofort lokal sichern; der Flush sendet später (Studie §4J).
      if (!online) {
        return { kind: "queued", item: enqueueNote(payload) };
      }
      setSending(true);
      try {
        const outcome = await submitNote(payload);
        if (outcome.ok) {
          return { kind: "sent", note: outcome.note };
        }
        // Transient (5xx/Netz) → puffern statt verlieren; hart → dem Werker melden.
        if (outcome.reason === "error") {
          return { kind: "queued", item: enqueueNote(payload) };
        }
        return { kind: "error", reason: outcome.reason, status: outcome.status };
      } finally {
        setSending(false);
      }
    },
    [author, online],
  );

  return { submit, sending };
}
