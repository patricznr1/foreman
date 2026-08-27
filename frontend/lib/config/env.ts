// ============================================================
//  FOREMAN Frontend — lib/config/env.ts
//  Zweck: Startprüfung der Umgebungsvariablen. Was im Betrieb nie geraten
//         werden darf, wird hier beim Serverstart eingefordert — nicht erst
//         dann, wenn ein Werker sich anmeldet.
//  Architektur-Einordnung: Laufzeit-Konfiguration (Schicht 0). Bewusst OHNE
//         Import aus `lib/auth/session.ts`: das Modul zieht `next/headers` und
//         gehört damit in den Anfrage-Pfad, nicht in den Startpfad.
// ============================================================

/**
 * Im Betrieb MUSS `FOREMAN_API_URL` gesetzt sein.
 *
 * `backendUrl()` in `lib/auth/session.ts` fällt ohne die Variable auf
 * `http://localhost:8000` zurück. Das ist für die lokale Entwicklung richtig und
 * im Betrieb immer falsch: Die Adresse zeigt ins Leere, und der Fehler taucht
 * erst beim ersten Anmeldeversuch auf — dort getarnt als „Dienst nicht
 * erreichbar". Diese Prüfung bricht stattdessen den Start ab, an der Ursache.
 *
 * Der Parameter ist für den Test da; im Betrieb liest sie `process.env`.
 */
export function assertBackendUrlConfigured(env: NodeJS.ProcessEnv = process.env): void {
  if (env.NODE_ENV !== "production") {
    return;
  }
  const configured = env.FOREMAN_API_URL;
  if (configured === undefined || configured.trim() === "") {
    throw new Error(
      "FOREMAN_API_URL ist nicht gesetzt. Im Betrieb wird die Backend-Adresse nicht " +
        "geraten — bitte die Variable am Frontend-Service setzen (siehe DEPLOY.md).",
    );
  }
}
