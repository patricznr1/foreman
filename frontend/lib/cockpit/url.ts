// ============================================================
//  FOREMAN Frontend — lib/cockpit/url.ts
//  Zweck: Reale Querlink-Ziele des Cockpits (Sektion A → B/C/E) und die Scope-URLs
//         der Föderations-Achse. Alle Ziele EXISTIEREN (B/C/E sind gebaut) — kein
//         graceful nötig. HITL: das Cockpit NAVIGIERT nur, es schaltet nichts.
//  Architektur-Einordnung: View-State (Schicht 2, rein, testbar).
// ============================================================
import type { CockpitScope } from "./types";

/** Cockpit-/Flotten-Route (Sektion A). */
export const FLEET_HREF = "/overview";

/** Zelle → Maschinen-Detail (Sektion B). */
export function machineHref(machineId: number): string {
  return `/machines/${machineId}`;
}

/** Prioritätsspalte → Alarme (Sektion C). */
export function alarmsHref(): string {
  return "/alarms";
}

/** Drift-Häufung/Risiko → Ausfallvorhersage der Maschine (Sektion E). */
export function predictionHref(machineId: number): string {
  return `/insights/prediction?machine=${machineId}`;
}

/** Scope-URL der Föderations-Achse (Klasse/Linie als Query-Parameter, deep-linkbar). */
export function scopeHref(scope: CockpitScope): string {
  const params = new URLSearchParams();
  if (scope.machineClass !== null) {
    params.set("class", scope.machineClass);
  }
  if (scope.lineId !== null) {
    params.set("line", String(scope.lineId));
  }
  const query = params.toString();
  return query.length > 0 ? `${FLEET_HREF}?${query}` : FLEET_HREF;
}
