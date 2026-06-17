// ============================================================
//  FOREMAN Frontend — lib/prediction/url.ts
//  Zweck: Die REALEN F-PRED/F-REC-Routen als relative BFF-Pfade (laufen über den
//         Proxy app/api/v1/[...path]; das JWT injiziert der BFF). Genau gegen den
//         Backend-Vertrag (reasoners/failure/router.py), nicht gegen Annahmen.
//  Architektur-Einordnung: Transport-Pfade (Schicht 1). Reine Funktion.
// ============================================================

/** POST — fordert eine frische Vorhersage an (On-Demand-Trigger). */
export function predictEndpoint(): string {
  return "/api/v1/reasoners/failure/predict";
}

/** GET — jüngste Vorhersage(n) einer Maschine (sortiert, jüngste zuerst). */
export function latestPredictionEndpoint(machineId: number): string {
  return `/api/v1/reasoners/failure/predictions?machine_id=${encodeURIComponent(String(machineId))}&limit=1`;
}

/** GET — Vorhersagen über mehrere Maschinen (Manager-Aggregat). */
export function predictionsEndpoint(limit: number): string {
  return `/api/v1/reasoners/failure/predictions?limit=${encodeURIComponent(String(limit))}`;
}

/** GET/POST — Empfehlung zu einer Vorhersage (POST erzeugt, GET liest die jüngste). */
export function recommendationEndpoint(predictionId: number): string {
  return `/api/v1/reasoners/failure/predictions/${encodeURIComponent(String(predictionId))}/recommendation`;
}
