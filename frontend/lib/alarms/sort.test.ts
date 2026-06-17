// ============================================================
//  FOREMAN Frontend — lib/alarms/sort.test.ts
//  Zweck: Prioritäts-Staffelung — kritisch oben, aktiv vor quittiert, Notfall vor
//         Kritisch, jüngste zuerst. Nicht chronologisch-flach.
// ============================================================
import { describe, expect, it } from "vitest";
import { NOW, alarm, machines, noNew, noShelf } from "./testing/fixtures";
import { sortAlarms } from "./sort";
import { buildAlarmViewModel } from "./view-model";

const vm = (over = {}) =>
  buildAlarmViewModel(alarm(over), { machines, shelf: noShelf, now: NOW, newIds: noNew });

describe("sortAlarms — Staffelung", () => {
  it("kritische immer oben, Journal unten", () => {
    const out = sortAlarms([
      vm({ severity: "info" }),
      vm({ severity: "critical" }),
      vm({ severity: "warning" }),
    ]);
    expect(out.map((v) => v.priority)).toEqual(["critical", "medium", "low"]);
    expect(out[0]?.priority).toBe("critical");
  });

  it("innerhalb des Tiers: aktiv vor quittiert", () => {
    const out = sortAlarms([
      vm({ id: 1, severity: "critical", acknowledged_at: "2026-06-17T08:00:00Z" }),
      vm({ id: 2, severity: "critical" }),
    ]);
    expect(out[0]?.id).toBe(2); // aktiv zuerst
  });

  it("Notfall vor Kritisch im selben Rot-Tier", () => {
    const out = sortAlarms([vm({ severity: "critical" }), vm({ severity: "emergency" })]);
    expect(out[0]?.severity).toBe("emergency");
  });

  it("jüngste zuerst bei gleicher Dringlichkeit", () => {
    const out = sortAlarms([
      vm({ id: 1, severity: "alarm", raised_at: "2026-06-17T07:00:00Z" }),
      vm({ id: 2, severity: "alarm", raised_at: "2026-06-17T08:00:00Z" }),
    ]);
    expect(out[0]?.id).toBe(2);
  });

  it("ist rein (mutiert die Eingabe nicht)", () => {
    const input = [vm({ severity: "info" }), vm({ severity: "critical" })];
    const before = input.map((v) => v.id);
    sortAlarms(input);
    expect(input.map((v) => v.id)).toEqual(before);
  });
});
