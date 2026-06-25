// ============================================================
//  FOREMAN Frontend — lib/machine/testing/card-fixture.ts
//  Zweck: Geteilte Test-Factory für MachineCardOut. EINE Quelle für die Fixtures
//         des Karten-Grids, der Gruppierung, der Karte und der Detail-Sicht — so
//         driftet kein Test-Doppel, wenn sich der Vertrag erweitert.
//  Architektur-Einordnung: Test-Hilfsmittel (Schicht 1), nur in *.test importiert.
// ============================================================
import type { MachineCardOut } from "@/lib/api/contracts";

/** Baut eine valide MachineCardOut mit sinnvollen Defaults; `overrides` ersetzt Felder. */
export function makeMachineCard(overrides: Partial<MachineCardOut> = {}): MachineCardOut {
  return {
    id: 1,
    label: "M-1",
    line_id: 1,
    machine_class: "servo_press",
    manufacturer: null,
    external_id: null,
    location: null,
    status: "healthy",
    open_alarm_count: 0,
    open_by_severity: {},
    last_alarm_at: null,
    components: [],
    data_points: [],
    stream: { active: true, last_reading_at: null },
    ...overrides,
  };
}
