// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/testing/fixtures.ts
//  Zweck: Test-Fabriken für die 3D-Linie — ein einzelner MachineStatusOut sowie
//         der reale 12-Maschinen-Park „Montagelinie 1" (IDs in Seed-Reihenfolge,
//         Drift/Gesund wie im Twin-Park). Nur in *.test importiert.
//  Architektur-Einordnung: Test-Hilfsmittel (Schicht 1).
// ============================================================
import type { MachineStatus, MachineStatusOut } from "@/lib/api/contracts";

/** Ein MachineStatusOut mit sinnvollen Defaults; `overrides` setzt einzelne Felder. */
export function makeMachineStatus(overrides: Partial<MachineStatusOut> = {}): MachineStatusOut {
  return {
    id: 1,
    label: "M-1",
    line_id: 1,
    machine_class: "servo_press",
    status: "healthy",
    open_alarm_count: 0,
    open_by_severity: {},
    last_alarm_at: null,
    ...overrides,
  };
}

interface ParkSpec {
  id: number;
  label: string;
  machineClass: string;
  status: MachineStatus;
}

// Der reale Twin-Park (12 Maschinen, alle „Montagelinie 1"). IDs in der Seed-
// Reihenfolge (alphabetische park_*.yaml: ax01–ax04 → 1–4, fd → 5/6, pr → 7–9,
// rb → 10/11, vs → 12) — so spiegelt id-Sortierung je Klasse die external-id-Folge.
// Drift-Maschinen wie im Szenario: FD-02, PR-01, PR-02, AX-02, AX-03, VS-01.
const PARK: readonly ParkSpec[] = [
  { id: 1, label: "Handling-Achse X", machineClass: "servo_axis", status: "healthy" },
  { id: 2, label: "Handling-Achse Y", machineClass: "servo_axis", status: "drift_active" },
  { id: 3, label: "Handling-Achse Z (vertikal)", machineClass: "servo_axis", status: "drift_active" },
  { id: 4, label: "Handling-Achse U", machineClass: "servo_axis", status: "healthy" },
  { id: 5, label: "Teilezufuehrung A", machineClass: "feeder", status: "healthy" },
  { id: 6, label: "Teilezufuehrung B", machineClass: "feeder", status: "drift_active" },
  { id: 7, label: "Fuegepresse 1", machineClass: "servo_press", status: "drift_active" },
  { id: 8, label: "Fuegepresse 2", machineClass: "servo_press", status: "open_warning" },
  { id: 9, label: "Fuegepresse 3", machineClass: "servo_press", status: "healthy" },
  { id: 10, label: "Bestueckroboter 1", machineClass: "robot", status: "healthy" },
  { id: 11, label: "Bestueckroboter 2 (Reserve)", machineClass: "robot", status: "healthy" },
  { id: 12, label: "Endkontrolle (Kamera)", machineClass: "vision", status: "open_warning" },
];

/** Der reale 12-Maschinen-Park als /overview-Maschinenliste (unsortiert wie aus der DB). */
export function makeParkMachines(): MachineStatusOut[] {
  return PARK.map((spec) =>
    makeMachineStatus({
      id: spec.id,
      label: spec.label,
      machine_class: spec.machineClass,
      status: spec.status,
    }),
  );
}
