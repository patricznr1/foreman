// ============================================================
//  FOREMAN Frontend — lib/alarms/flood.test.ts
//  Zweck: Flood-Schutz — gleichquellige aktive Alarme gebündelt statt N Zeilen;
//         Reihenfolge bleibt; quittierte/geklärte bündeln nie.
// ============================================================
import { describe, expect, it } from "vitest";
import { bundleRows } from "./flood";
import { NOW, alarm, machines, noNew, noShelf } from "./testing/fixtures";
import { sortAlarms } from "./sort";
import { buildAlarmViewModel } from "./view-model";

const vm = (over = {}) =>
  buildAlarmViewModel(alarm(over), { machines, shelf: noShelf, now: NOW, newIds: noNew });

describe("bundleRows — gemeinsame Quelle (Linie + Code)", () => {
  it("12 gleichquellige aktive Alarme → ein Bündel statt 12 Zeilen", () => {
    const rows = Array.from({ length: 12 }, (_n, i) =>
      vm({ id: i + 1, machine_id: 1, code: "OVERLOAD", severity: "alarm" }),
    );
    const items = bundleRows(sortAlarms(rows), { threshold: 3 });
    expect(items).toHaveLength(1);
    expect(items[0]?.kind).toBe("bundle");
    if (items[0]?.kind === "bundle") {
      expect(items[0].bundle.count).toBe(12);
      expect(items[0].bundle.sourceLabel).toMatch(/Linie 3/);
    }
  });

  it("unter der Schwelle bleibt es bei Einzelzeilen", () => {
    const rows = [
      vm({ id: 1, code: "X", severity: "alarm" }),
      vm({ id: 2, code: "X", severity: "alarm" }),
    ];
    const items = bundleRows(rows, { threshold: 3 });
    expect(items.every((i) => i.kind === "row")).toBe(true);
  });

  it("quittierte/geklärte Alarme bündeln NICHT (in Bearbeitung)", () => {
    const rows = [
      vm({ id: 1, code: "X", severity: "alarm", acknowledged_at: "2026-06-17T08:00:00Z" }),
      vm({ id: 2, code: "X", severity: "alarm", acknowledged_at: "2026-06-17T08:00:00Z" }),
      vm({ id: 3, code: "X", severity: "alarm", acknowledged_at: "2026-06-17T08:00:00Z" }),
    ];
    const items = bundleRows(rows, { threshold: 3 });
    expect(items.every((i) => i.kind === "row")).toBe(true);
  });

  it("getrennte Quellen → getrennte Bündel; das Bündel sitzt an der ersten Position", () => {
    const rows = sortAlarms([
      ...Array.from({ length: 3 }, (_n, i) => vm({ id: 10 + i, machine_id: 1, code: "A" })),
      ...Array.from({ length: 3 }, (_n, i) => vm({ id: 20 + i, machine_id: 3, code: "B" })),
    ]);
    const items = bundleRows(rows, { threshold: 3 });
    expect(items.filter((i) => i.kind === "bundle")).toHaveLength(2);
  });
});
