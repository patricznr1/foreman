// ============================================================
//  FOREMAN Frontend — lib/memory/url.ts
//  Zweck: Die REALE Archiv-Route als relativer BFF-Pfad (laeuft ueber den Proxy
//         app/api/v1/[...path]; das JWT injiziert der BFF). Genau gegen den
//         Backend-Vertrag (archive/router.py: q, machine_id, sources, k 1 bis 50),
//         nicht gegen Annahmen. Read-only: die Suche ist Abruf, keine Aktorik.
//  Architektur-Einordnung: Transport-Pfad (Schicht 1). Reine Funktion.
// ============================================================
import type { SourceType } from "./types";

/**
 * Trefferzahl der reinen NOTIZ-Suche (Kontextvorschlag der Erfassung J).
 * Das Backend erlaubt 1 bis 50 und gibt 5 vor; fuer eine brauchbare
 * Vorschlagsliste fordert die Sicht etwas mehr.
 *
 * GILT NICHT FUERS ARCHIV. Dessen Ausgabelaenge steht seit dem 27.08.2026 an
 * genau einer Stelle im Backend (`ARCHIV_AUSGABELAENGE`), und
 * `searchArchiveEndpoint` schickt gar kein `k` mehr mit. Dass diese Konstante
 * frueher fuer BEIDE galt, war die Haelfte des Befunds C-083 — drei Orte, drei
 * verschiedene Zahlen.
 */
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

/**
 * GET — Archiv-Suche ueber Notizen + Wartung + Alarme + Gedaechtnis
 * (relevanteste zuerst, ohne Score). `sources` waehlt die Quellen (CSV; das
 * Backend akzeptiert CSV oder wiederholt). Leer oder null = der Backend-Default
 * (alle Quellen).
 *
 * OHNE `k`, UND DAS IST DER PUNKT: Die Ausgabelaenge steht seit dem 27.08.2026
 * an genau EINER Stelle — `ARCHIV_AUSGABELAENGE` im Backend. Die Anzeige erbt
 * sie, statt eine eigene zu fuehren.
 *
 * Vorher stand sie an drei Orten verschieden (Backend 5, hier 12, Messwerkzeug
 * 10, siehe C-083). Gemessen wurde damit eine Ausgabelaenge, die niemand zu
 * sehen bekam — und die Aussage ueber Verdraengung galt fuer ein System, das so
 * nicht ausgeliefert wird. Zwei Zahlen, die dasselbe bedeuten sollen, laufen
 * frueher oder spaeter auseinander; eine kann das nicht.
 */
export function searchArchiveEndpoint(
  query: string,
  machineId: number | null = null,
  sources: SourceType[] | null = null,
): string {
  const params = new URLSearchParams();
  params.set("q", query);
  if (machineId !== null) {
    params.set("machine_id", String(machineId));
  }
  if (sources !== null && sources.length > 0) {
    params.set("sources", sources.join(","));
  }
  return `/api/v1/archive/search?${params.toString()}`;
}
