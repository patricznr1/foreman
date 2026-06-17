// ============================================================
//  FOREMAN Frontend — lib/memory/url.ts
//  Zweck: Die REALE F-SEM-Route als relativer BFF-Pfad (laeuft ueber den Proxy
//         app/api/v1/[...path]; das JWT injiziert der BFF). Genau gegen den
//         Backend-Vertrag (notes/router.py: q, machine_id, k 1 bis 50), nicht
//         gegen Annahmen. Read-only: die Suche ist Abruf, keine Aktorik.
//  Architektur-Einordnung: Transport-Pfad (Schicht 1). Reine Funktion.
// ============================================================

/** Default-Trefferzahl der Sicht (Backend erlaubt 1 bis 50, Default 5; die Sicht
 *  fordert etwas mehr fuer eine brauchbare Verdichtung). */
export const DEFAULT_SEARCH_K = 12;

/** GET — Bedeutungssuche ueber Schichtnotizen (aehnlichste zuerst, ohne Score). */
export function searchNotesEndpoint(
  query: string,
  machineId: number | null = null,
  k: number = DEFAULT_SEARCH_K,
): string {
  const params = new URLSearchParams();
  params.set("q", query);
  if (machineId !== null) {
    params.set("machine_id", String(machineId));
  }
  params.set("k", String(k));
  return `/api/v1/worker_notes/search?${params.toString()}`;
}
