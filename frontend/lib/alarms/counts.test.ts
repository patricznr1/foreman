// ============================================================
//  FOREMAN Frontend — lib/alarms/counts.test.ts
//  Zweck: Prioritäts-Zähler aus Zeilen UND live aus dem overview-Aggregat.
// ============================================================
import { describe, expect, it } from "vitest";
import type { FleetOverviewOut } from "@/lib/api/contracts";
import { countByPriority, countByPriorityFromOverview, countDrift, hasCritical } from "./counts";
import { NOW, alarm, machines, noNew, noShelf } from "./testing/fixtures";
import { buildAlarmViewModel } from "./view-model";

const vm = (over = {}) =>
  buildAlarmViewModel(alarm(over), { machines, shelf: noShelf, now: NOW, newIds: noNew });

describe("countByPriority — offene Alarme je Tier", () => {
  it("zählt nach Priorität, ohne geklärte", () => {
    const counts = countByPriority([
      vm({ severity: "critical" }),
      vm({ severity: "emergency" }),
      vm({ severity: "alarm" }),
      vm({ severity: "warning", cleared_at: "2026-06-17T09:00:00Z" }), // geklärt → zählt nicht
    ]);
    expect(counts.critical).toBe(2);
    expect(counts.high).toBe(1);
    expect(counts.medium).toBe(0);
  });

  it("countDrift zählt nur offene Drift-Warnungen", () => {
    expect(countDrift([vm({ code: "DRIFT" }), vm({ code: null }), vm({ code: "DRIFT" })])).toBe(2);
  });
});

describe("countByPriorityFromOverview — Live-Zähler aus dem Aggregat", () => {
  const overview: FleetOverviewOut = {
    machines: [
      {
        id: 1,
        label: "Presse 1",
        line_id: 3,
        machine_class: null,
        status: "open_warning",
        open_alarm_count: 3,
        open_by_severity: { critical: 1, warning: 2 },
        last_alarm_at: null,
      },
      {
        id: 3,
        label: "Pumpe 3",
        line_id: 7,
        machine_class: null,
        status: "open_warning",
        open_alarm_count: 1,
        open_by_severity: { alarm: 1 },
        last_alarm_at: null,
      },
    ],
    by_status: { healthy: 0, drift_active: 0, open_warning: 2 },
    open_alarm_total: 4,
  };

  it("summiert open_by_severity und mappt auf Tiers", () => {
    const counts = countByPriorityFromOverview(overview);
    expect(counts.critical).toBe(1);
    expect(counts.medium).toBe(2);
    expect(counts.high).toBe(1);
  });

  it("respektiert den Scope-Filter (nur sichtbare Maschinen)", () => {
    const counts = countByPriorityFromOverview(overview, (_id, lineId) => lineId === 3);
    expect(counts.critical).toBe(1);
    expect(counts.medium).toBe(2);
    expect(counts.high).toBe(0); // Pumpe (Linie 7) ausgeblendet
  });

  it("hasCritical erkennt offene kritische Alarme", () => {
    expect(hasCritical(countByPriorityFromOverview(overview))).toBe(true);
  });
});
