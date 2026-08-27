// ============================================================
//  FOREMAN Frontend — lib/api/backend-error.ts
//  Zweck: Trennt im BFF „die Anfrage war das Problem" (4xx) von „der Dienst ist
//         das Problem" (5xx, Netz, Zeitüberschreitung). Ohne diese Trennung
//         meldet die Fassade eine fehlerhafte Eingabe als Ausfall — und die
//         Fehlersuche geht ins Netz statt ins Eingabefeld.
//  Architektur-Einordnung: Transport-Vertrag (Schicht 1), server-seitig genutzt.
//  Quelle: FastAPI-Validierungsformat (RequestValidationError → 422 mit
//          `detail: [{ loc, msg, type }]`), Backend-Schema schemas/auth.py.
// ============================================================

/**
 * Ob dieser Backend-Status die ANFRAGE beanstandet (4xx) statt den Dienst zu
 * melden (5xx). Nur 4xx darf im BFF zu einer Eingabe-Meldung werden — alles
 * andere bleibt ein Ausfall (502).
 */
export function isClientError(status: number): boolean {
  return status >= 400 && status < 500;
}

/**
 * Zieht aus einem FastAPI-Validierungsfehler (422) die beanstandeten Feldnamen.
 *
 * FastAPI antwortet mit `{ "detail": [{ "loc": ["body", "email"], … }] }`; der
 * LETZTE Eintrag von `loc` ist der Feldname. Ein Body, der dieser Form nicht
 * entspricht, liefert eine leere Liste — es wird nichts geraten, denn ein
 * geratener Feldname erzeugt genau die irreführende Meldung, gegen die diese
 * Datei gebaut ist.
 */
export function invalidFields(payload: unknown): string[] {
  if (typeof payload !== "object" || payload === null) {
    return [];
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (!Array.isArray(detail)) {
    return [];
  }
  const fields: string[] = [];
  for (const issue of detail) {
    if (typeof issue !== "object" || issue === null) {
      continue;
    }
    const loc = (issue as { loc?: unknown }).loc;
    if (!Array.isArray(loc)) {
      continue;
    }
    const field = loc[loc.length - 1];
    if (typeof field === "string") {
      fields.push(field);
    }
  }
  return fields;
}
