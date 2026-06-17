// ============================================================
//  FOREMAN Frontend — lib/alarms/testing/fixtures.ts
//  Zweck: Deterministische Test-Fixtures für die Alarm-View-State-Logik. Ein
//         AlarmRead-Builder + Maschinen-Stammdaten, damit die reinen Module ohne
//         UI/Transport gegen realistische Daten geprüft werden.
//  Architektur-Einordnung: Test-Hilfen (nur Tests).
// ============================================================
import type { AlarmRead } from "@/lib/api/contracts";
import type { MachineMeta } from "../types";

let seq = 1000;

/** AlarmRead mit sinnvollen Defaults; alles überschreibbar. */
export function alarm(over: Partial<AlarmRead> = {}): AlarmRead {
  seq += 1;
  return {
    id: seq,
    machine_id: 1,
    component_id: null,
    data_point_id: null,
    code: null,
    message: "Lagertemperatur hoch",
    severity: "warning",
    category: "process",
    raised_at: "2026-06-17T08:00:00Z",
    cleared_at: null,
    acknowledged_at: null,
    acknowledged_by: null,
    created_at: "2026-06-17T08:00:00Z",
    ...over,
  };
}

export const machines: ReadonlyMap<number, MachineMeta> = new Map([
  [1, { label: "Presse 1", lineId: 3 }],
  [2, { label: "Spindel 2", lineId: 3 }],
  [3, { label: "Pumpe 3", lineId: 7 }],
]);

export const NOW = Date.parse("2026-06-17T09:00:00Z");
export const noShelf: ReadonlyMap<number, number> = new Map();
export const noNew: ReadonlySet<number> = new Set();
