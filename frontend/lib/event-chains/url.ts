// ============================================================
//  FOREMAN Frontend — lib/event-chains/url.ts
//  Zweck: Die REALEN F-REC-Routen der Ereignisketten als relative BFF-Pfade
//         (laufen über app/api/v1/[...path]; das JWT injiziert der BFF). Gegen den
//         Backend-Vertrag (reasoners/event_chain/router.py), nicht gegen Annahmen.
//         Plus Querlink-Ziele (Anker-Alarm → C, Maschine → B).
//  Architektur-Einordnung: Transport-/Navigations-Pfade (Schicht 1). Reine Funktion.
// ============================================================

/** POST — rekonstruiert on-demand eine Kette um einen Anker-Alarm. */
export function reconstructEndpoint(): string {
  return "/api/v1/reasoners/event_chain/reconstruct";
}

/** GET — gespeicherte Ketten-Erklärungen (optional je Maschine, jüngste zuerst). */
export function explanationsEndpoint(machineId?: number | null): string {
  const base = "/api/v1/reasoners/event_chain/explanations";
  if (machineId == null) {
    return base;
  }
  return `${base}?machine_id=${encodeURIComponent(String(machineId))}`;
}

/** GET — eine einzelne Erklärung inkl. eingefrorener Kette + Schwester-Referenzen. */
export function explanationEndpoint(explanationId: number): string {
  return `/api/v1/reasoners/event_chain/explanations/${encodeURIComponent(String(explanationId))}`;
}

/** GET — die eingefrorenen Schwester-Referenzen einer Erklärung. */
export function siblingsEndpoint(explanationId: number): string {
  return `/api/v1/reasoners/event_chain/explanations/${encodeURIComponent(String(explanationId))}/siblings`;
}

// — Navigationsziele (Kontextnavigation, Studie §3.3) —

/** Sektion C — der Original-Alarm (Severity-Farbe lebt dort, nicht in der Kette). */
export function alarmsHref(): string {
  return "/alarms";
}

/** Sektion B — die Maschine. */
export function machineHref(machineId: number): string {
  return `/machines/${encodeURIComponent(String(machineId))}`;
}

/** Sektion D — Ketten-Sicht, optional vorbelegt mit Anker-Alarm (Trigger),
 *  Maschinen-Filter und/oder einer konkret zu öffnenden Erklärung (Deep-Link). */
export function chainsHref(params?: {
  anchor?: number;
  machine?: number;
  explanation?: number;
}): string {
  const base = "/insights/chains";
  const search = new URLSearchParams();
  if (params?.anchor != null) {
    search.set("anchor", String(params.anchor));
  }
  if (params?.machine != null) {
    search.set("machine", String(params.machine));
  }
  if (params?.explanation != null) {
    search.set("explanation", String(params.explanation));
  }
  const query = search.toString();
  return query ? `${base}?${query}` : base;
}
