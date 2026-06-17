// ============================================================
//  FOREMAN Frontend — lib/machine/url.ts
//  Zweck: Relative BFF-Routen der Maschinen-Detail-Sicht. Alle Aufrufe laufen über
//         den Next-Route-Handler-Proxy (app/api/v1/[...path]), der das JWT aus dem
//         httpOnly-Cookie als Bearer injiziert (kein Token im Browser-JS, §21.4).
//         Read-only: keine Aktorik (HITL liegt in Navigation/Anforderung).
//  Architektur-Einordnung: Transport-Adapter (Schicht 1/2, rein).
// ============================================================

/** Stammdaten einer Einzelmaschine. */
export function machineUrl(machineId: number): string {
  return `/api/v1/machines/${machineId}`;
}

/** Aggregierter Sensortrend + statisches Normalband (datapoint NAME, hours 1–168). */
export function machineTrendUrl(machineId: number, datapoint: string, hours: number): string {
  return `/api/v1/machines/${machineId}/trend?datapoint=${encodeURIComponent(datapoint)}&hours=${hours}`;
}

/** Datenpunkte einer Maschine (Sensorauswahl). */
export function dataPointsUrl(machineId: number): string {
  return `/api/v1/data_points?machine_id=${machineId}`;
}

/** Komponenten einer Maschine (Spezifikation). */
export function componentsUrl(machineId: number): string {
  return `/api/v1/components?machine_id=${machineId}`;
}

/** Maschinen-Liste (für die /machines-Übersicht). */
export function machinesUrl(limit: number): string {
  return `/api/v1/machines?limit=${limit}`;
}

/** Wartungs-/Prüfhistorie einer Maschine (blätterbar). */
export function maintenanceEventsUrl(machineId: number, limit: number, offset: number): string {
  return `/api/v1/maintenance_events?machine_id=${machineId}&limit=${limit}&offset=${offset}`;
}

/** Werker-Notizen einer Maschine (blätterbar; Text backend-seitig NER-maskiert). */
export function workerNotesUrl(machineId: number, limit: number, offset: number): string {
  return `/api/v1/worker_notes?machine_id=${machineId}&limit=${limit}&offset=${offset}`;
}
