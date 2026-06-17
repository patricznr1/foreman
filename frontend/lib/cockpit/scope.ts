// ============================================================
//  FOREMAN Frontend — lib/cockpit/scope.ts
//  Zweck: Geltungsbereich des Cockpits (Föderations-Achse §3.3/§4A). Da das Backend
//         /overview bereits serverseitig scope-gefiltert liefert (manager = alle,
//         shift_lead = seine Linien) UND kein line:/class:-Live-Thema existiert,
//         ist die Klassen-/Linien-Wahl ein reiner CLIENT-Filter über den bereits
//         autorisierten Maschinen-Satz — kein Re-Abo, kein Live-Event (per Vertrag).
//         Die Mehr-WERK-Ebene bleibt markiertes Zielbild (Single-Tenant).
//  Architektur-Einordnung: View-State (Schicht 2, rein, testbar).
// ============================================================
import type { MachineStatusOut } from "@/lib/api/contracts";
import type { ScopeCrumb } from "@/components/shell/scope-breadcrumb";

import type { CockpitScope } from "./types";
import { FLEET_HREF, scopeHref } from "./url";

/** Liest den Scope aus rohen Query-Werten (URL-Parameter), defensiv. */
export function parseScope(params: {
  class?: string | string[] | null;
  line?: string | string[] | null;
}): CockpitScope {
  const rawClass = Array.isArray(params.class) ? params.class[0] : params.class;
  const machineClass = rawClass != null && rawClass.length > 0 ? rawClass : null;

  // Strikte Ganzzahl-Prüfung: "3abc"/"2.5" sind KEINE gültige Linien-ID (Number.parseInt
  // wäre zu nachsichtig und würde "3abc" → 3 akzeptieren).
  const rawLine = Array.isArray(params.line) ? params.line[0] : params.line;
  const normalizedLine = rawLine?.trim() ?? "";
  const lineId = /^\d+$/.test(normalizedLine) ? Number(normalizedLine) : null;

  return { machineClass, lineId };
}

/** Filtert die Maschinenliste auf den Scope (Klasse und/oder Linie). */
export function filterByScope(machines: MachineStatusOut[], scope: CockpitScope): MachineStatusOut[] {
  return machines.filter(
    (machine) =>
      (scope.machineClass === null || machine.machine_class === scope.machineClass) &&
      (scope.lineId === null || machine.line_id === scope.lineId),
  );
}

/** Ist der Scope eingeengt (nicht die ganze Flotte)? */
export function isScoped(scope: CockpitScope): boolean {
  return scope.machineClass !== null || scope.lineId !== null;
}

/**
 * Baut den Breadcrumb-Pfad der Föderations-Achse: Flotte ▸ Klasse ▸ Linie. Die
 * Mehr-WERK-Ebene ist NICHT enthalten (Zielbild-Marker rendert der View separat).
 * Alle Krümel tragen ihren href; die letzte Position kennzeichnet die Komponente
 * als aktuell (aria-current) und unterdrückt dort den Link.
 */
export function scopeCrumbs(scope: CockpitScope): ScopeCrumb[] {
  const crumbs: ScopeCrumb[] = [{ label: "Flotte", href: FLEET_HREF }];
  if (scope.machineClass !== null) {
    crumbs.push({
      label: `Klasse: ${scope.machineClass}`,
      href: scopeHref({ machineClass: scope.machineClass, lineId: null }),
    });
  }
  if (scope.lineId !== null) {
    crumbs.push({ label: `Linie ${scope.lineId}`, href: scopeHref(scope) });
  }
  return crumbs;
}
