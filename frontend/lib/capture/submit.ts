// ============================================================
//  FOREMAN Frontend — lib/capture/submit.ts
//  Zweck: Den Erfassungs-Entwurf in den REALEN POST-Body übersetzen und die
//         Antwort in ein SubmitOutcome interpretieren. Reine Helfer (payload/
//         status) sind ohne Netz testbar; submitNote() komponiert sie mit fetch
//         (injizierbar). Der Pfad geht über den BFF-Proxy (JWT serverseitig).
//         classification wird mitgesendet (Werker-Kategorie) — das Backend nimmt
//         das Feld heute noch nicht an und verwirft es still (Anschlusspunkt).
//  Architektur-Einordnung: Transport-Komposition (Schicht 1). Reine + IO-Funktion.
// ============================================================
import type { WorkerNoteCreate, WorkerNoteRead } from "@/lib/api/contracts";
import type { CaptureDraft, SubmitOutcome } from "./types";
import { createNoteEndpoint } from "./url";

/**
 * Baut den POST-Body aus dem Entwurf. Reine Funktion. Leere optionale Felder werden
 * WEGGELASSEN (das Backend setzt dann None). `author` ist die eigene user_id im
 * Klartext — serverseitig zu einem HMAC-Token pseudonymisiert (§8), nie als Klartext
 * gespeichert; das Frontend hält ihn nur transient.
 */
export function buildNotePayload(draft: CaptureDraft, author: string | null): WorkerNoteCreate {
  const payload: WorkerNoteCreate = { text: draft.text.trim() };
  if (draft.machineId !== null) {
    payload.machine_id = draft.machineId;
  }
  const shift = draft.shift?.trim();
  if (shift) {
    payload.shift = shift;
  }
  if (draft.classification !== null) {
    payload.classification = draft.classification;
  }
  const trimmedAuthor = author?.trim();
  if (trimmedAuthor) {
    payload.author = trimmedAuthor;
  }
  return payload;
}

/** Ob ein Entwurf abschickbar ist — Pflichtfeld `text` darf nicht leer sein. */
export function isSubmittable(draft: CaptureDraft): boolean {
  return draft.text.trim().length > 0;
}

/** HTTP-Status → Outcome-Klasse. 201/200 = ok; 422 hart (Validierung); 401/403 hart;
 *  alles andere (5xx/Netz/0) transient. Reine Funktion. */
export function classifyStatus(
  status: number,
): "ok" | "validation" | "unauthorized" | "forbidden" | "error" {
  if (status === 201 || status === 200) {
    return "ok";
  }
  if (status === 422) {
    return "validation";
  }
  if (status === 401) {
    return "unauthorized";
  }
  if (status === 403) {
    return "forbidden";
  }
  return "error";
}

/**
 * Sendet eine Notiz an den worker_notes-POST über den BFF-Proxy. `fetchImpl` ist
 * injizierbar (Tests). Netz-/Parse-Fehler werden als transienter `error` gemeldet
 * (die Queue darf erneut versuchen). Nie ein throw nach außen.
 */
/** Client-Timeout: ein hängendes Netz darf den Sende-/Flush-Pfad nicht blockieren —
 *  ein Abbruch zählt als transienter Fehler (puffern + später erneut). */
const SUBMIT_TIMEOUT_MS = 10_000;

export async function submitNote(
  payload: WorkerNoteCreate,
  fetchImpl: typeof fetch = fetch,
): Promise<SubmitOutcome> {
  try {
    const response = await fetchImpl(createNoteEndpoint(), {
      method: "POST",
      credentials: "same-origin",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(SUBMIT_TIMEOUT_MS),
    });
    const reason = classifyStatus(response.status);
    if (reason === "ok") {
      const note = (await response.json()) as WorkerNoteRead;
      return { ok: true, note };
    }
    return { ok: false, reason, status: response.status };
  } catch {
    return { ok: false, reason: "error" };
  }
}
