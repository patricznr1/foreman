// ============================================================
//  FOREMAN Frontend — lib/machine/url.test.ts
//  Zweck: Sichert die relativen BFF-Routen der Maschinen-Detail-Sicht.
// ============================================================
import { describe, expect, it } from "vitest";

import {
  componentsUrl,
  dataPointsUrl,
  machineTrendUrl,
  machineUrl,
  machinesUrl,
  maintenanceEventsUrl,
  workerNotesUrl,
} from "./url";

describe("BFF-Routen", () => {
  it("machineUrl → Einzelmaschine", () => {
    expect(machineUrl(7)).toBe("/api/v1/machines/7");
  });

  it("machineTrendUrl → datapoint + hours (encodiert)", () => {
    expect(machineTrendUrl(7, "spindle_temp", 24)).toBe(
      "/api/v1/machines/7/trend?datapoint=spindle_temp&hours=24",
    );
  });

  it("dataPointsUrl / componentsUrl → nach Maschine gefiltert", () => {
    expect(dataPointsUrl(7)).toBe("/api/v1/data_points?machine_id=7");
    expect(componentsUrl(7)).toBe("/api/v1/components?machine_id=7");
  });

  it("maintenanceEventsUrl / workerNotesUrl → Maschine + Pagination", () => {
    expect(maintenanceEventsUrl(7, 25, 0)).toBe(
      "/api/v1/maintenance_events?machine_id=7&limit=25&offset=0",
    );
    expect(workerNotesUrl(7, 25, 50)).toBe(
      "/api/v1/worker_notes?machine_id=7&limit=25&offset=50",
    );
  });

  it("machinesUrl → Liste mit Limit", () => {
    expect(machinesUrl(100)).toBe("/api/v1/machines?limit=100");
  });
});
