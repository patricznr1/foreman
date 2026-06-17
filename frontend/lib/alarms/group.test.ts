// ============================================================
//  FOREMAN Frontend — lib/alarms/group.test.ts
//  Zweck: Gruppierung nach Priorität / Bereich / Maschine; Ordnung erhalten.
// ============================================================
import { describe, expect, it } from "vitest";
import { groupAlarms } from "./group";
import { NOW, alarm, machines, noNew, noShelf } from "./testing/fixtures";
import { sortAlarms } from "./sort";
import { buildAlarmViewModel } from "./view-model";

const vm = (over = {}) =>
  buildAlarmViewModel(alarm(over), { machines, shelf: noShelf, now: NOW, newIds: noNew });

const rows = sortAlarms([
  vm({ id: 1, machine_id: 1, severity: "critical" }),
  vm({ id: 2, machine_id: 2, severity: "warning" }),
  vm({ id: 3, machine_id: 3, severity: "alarm" }),
]);

describe("groupAlarms", () => {
  it("Priorität: Tiers in fester Reihenfolge, leere weggelassen", () => {
    const groups = groupAlarms(rows, "priority");
    expect(groups.map((g) => g.priority)).toEqual(["critical", "high", "medium"]);
    expect(groups[0]?.label).toBe("Kritisch");
  });

  it("Maschine: ein Bucket je Maschine, dringlichste Maschine zuerst", () => {
    const groups = groupAlarms(rows, "machine");
    expect(groups[0]?.label).toBe("Presse 1"); // hat den kritischen Alarm
    expect(groups).toHaveLength(3);
  });

  it("Bereich: Buckets nach Linie", () => {
    const groups = groupAlarms(rows, "area");
    const labels = groups.map((g) => g.label);
    expect(labels).toContain("Linie 3");
    expect(labels).toContain("Linie 7");
  });
});
