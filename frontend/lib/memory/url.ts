// ============================================================
//  FOREMAN Frontend — lib/memory/url.ts
//  Zweck: Die REALE Archiv-Route als relativer BFF-Pfad (laeuft ueber den Proxy
//         app/api/v1/[...path]; das JWT injiziert der BFF). Genau gegen den
//         Backend-Vertrag (archive/router.py: q, machine_id, sources, k 1 bis 50),
//         nicht gegen Annahmen. Read-only: die Suche ist Abruf, keine Aktorik.
//  Architektur-Einordnung: Transport-Pfad (Schicht 1). Reine Funktion.
// ============================================================
import type { SourceType } from "./types";

/** Default-Trefferzahl der Sicht (Backend erlaubt 1 bis 50, Default 5; die Sicht
 *  fordert etwas mehr fuer eine brauchbare Liste). */
export const DEFAULT_SEARCH_K = 12;

/** GET — reine Notiz-Suche (alter F-SEM-Endpoint, weiterhin vom Kontextvorschlag der
 *  Erfassung J genutzt; das Archiv 1c nutzt `searchArchiveEndpoint`). */
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

/** GET — Archiv-Suche ueber Notizen + Wartung + Alarme (relevanteste zuerst, ohne Score).
 *  `sources` waehlt die Quellen (CSV; das Backend akzeptiert CSV oder wiederholt). Leer
 *  oder null = der Backend-Default (alle Quellen). */
export function searchArchiveEndpoint(
  query: string,
  machineId: number | null = null,
  sources: SourceType[] | null = null,
  k: number = DEFAULT_SEARCH_K,
): string {
  const params = new URLSearchParams();
  params.set("q", query);
  if (machineId !== null) {
    params.set("machine_id", String(machineId));
  }
  if (sources !== null && sources.length > 0) {
    params.set("sources", sources.join(","));
  }
  params.set("k", String(k));
  return `/api/v1/archive/search?${params.toString()}`;
}
