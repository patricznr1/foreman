// ============================================================
//  FOREMAN Frontend — lib/platform/url.ts
//  Zweck: BFF-Anschluss der Sektion I — baut die relativen Pfade der zwei
//         Read-APIs (GET /api/v1/topology, GET /api/v1/audit, §22) für den
//         generischen BFF-Proxy (app/api/v1/[...path]). KEIN eigener Route-Handler
//         nötig: der Catch-all reicht httpOnly-Cookie→Bearer durch (wie für alle
//         Sektionen). Die Audit-Query stammt aus dem reinen Filter-Modul.
//  Architektur-Einordnung: reine Pfad-Logik (Schicht 2).
// ============================================================
import { auditQueryEntries, type AuditFilter } from "./audit-filter";

/** Optionen der Topologie-Probe (§22.2): live proben (Smoke-Marker) + Frischefenster. */
export interface TopologyOptions {
  probe: boolean;
  freshWithinMinutes?: number;
}

/**
 * GET /api/v1/topology — ehrlich abgeleitete Systemtopologie. `probe=false`
 * unterdrückt die Substrat-Live-Probe (kein Smoke-Marker); `freshWithinMinutes`
 * setzt das „verbunden"-Fenster (Backend-Default 60, Bereich 1..10080).
 */
export function topologyEndpoint(options: TopologyOptions): string {
  const params = new URLSearchParams();
  // Explizit beide Belegungen senden — der Refresh ist bewusst/sichtbar (§22.2).
  params.set("probe", options.probe ? "true" : "false");
  if (options.freshWithinMinutes !== undefined) {
    params.set("fresh_within_minutes", String(options.freshWithinMinutes));
  }
  return `/api/v1/topology?${params.toString()}`;
}

/**
 * GET /api/v1/audit — unveränderlicher Audit-Trail (jüngste zuerst). Die Query
 * kommt vollständig aus dem reinen Filter-Modul (gesetzte Felder + Pagination).
 */
export function auditEndpoint(filter: AuditFilter): string {
  const params = new URLSearchParams();
  for (const [key, value] of auditQueryEntries(filter)) {
    params.set(key, value);
  }
  return `/api/v1/audit?${params.toString()}`;
}

/**
 * Mappt einen HTTP-Status auf den message-Key der Fünf-Zustände-Hülle
 * (`friendlyError`): 401 → Sitzung abgelaufen, 403 → kein Zugriff, sonst generisch.
 */
export function fetchErrorKey(status: number): string {
  if (status === 401) {
    return "unauthorized";
  }
  if (status === 403) {
    return "forbidden";
  }
  return "load-failed";
}
