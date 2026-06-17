// ============================================================
//  FOREMAN Frontend — lib/capture/url.ts
//  Zweck: Die REALE Erfassungs-Route als relativer BFF-Pfad (POST, laeuft ueber
//         den Proxy app/api/v1/[...path]; das JWT injiziert der BFF aus dem
//         httpOnly-Cookie). Gegen den Backend-Vertrag (api/routers/worker_notes.py:
//         WorkerNoteCreate), nicht gegen Annahmen. Eine Notiz erfassen ist eine
//         menschliche Daten-Eingabe — keine Anlagen-Aktorik.
//  Architektur-Einordnung: Transport-Pfad (Schicht 1). Reine Funktion.
// ============================================================

/** POST — eine Werker-Notiz erfassen (worker_notes-CRUD, §4). */
export function createNoteEndpoint(): string {
  return "/api/v1/worker_notes";
}
