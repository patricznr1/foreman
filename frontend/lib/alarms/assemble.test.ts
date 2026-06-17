// ============================================================
//  FOREMAN Frontend — lib/alarms/assemble.test.ts
//  Zweck: Die Pipeline als Ganzes (Akzeptanz): Staffelung (kritisch oben), Zähler,
//         Gruppierung, Flood-Bündelung + Aufklappen, Scope-Filter, Lebenszyklus-
//         Filter, Drift-Klasse. Deterministisch, ohne UI.
// ============================================================
import { describe, expect, it } from "vitest";
import { GROUP_MODES, assembleAlarmView, defaultFilter } from "./assemble";
import { NOW, alarm, machines, noNew, noShelf } from "./testing/fixtures";

const base = {
  machines,
  shelf: noShelf,
  now: NOW,
  newIds: noNew,
  filter: defaultFilter(),
  groupMode: "priority" as const,
  expandedBundles: new Set<string>(),
};

describe("assembleAlarmView — Staffelung & Kopf", () => {
  it("kritischer Gruppenkopf steht ganz oben", () => {
    const view = assembleAlarmView(
      [alarm({ severity: "info" }), alarm({ severity: "critical" }), alarm({ severity: "warning" })],
      base,
    );
    const firstHeader = view.rows.find((r) => r.kind === "header");
    expect(firstHeader?.kind === "header" && firstHeader.priority).toBe("critical");
    expect(view.rows[0]?.kind).toBe("header");
  });

  it("Zähler je Priorität (für '2 kritisch · …')", () => {
    const view = assembleAlarmView(
      [
        alarm({ severity: "critical" }),
        alarm({ severity: "critical" }),
        alarm({ severity: "warning" }),
        alarm({ code: "DRIFT", severity: "warning" }),
      ],
      base,
    );
    expect(view.counts.critical).toBe(2);
    expect(view.counts.medium).toBe(2);
    expect(view.driftCount).toBe(1);
  });

  it("Live-Zähler aus dem Aggregat überschreiben die Zeilen-Zählung im Kopf", () => {
    const live = { critical: 9, high: 0, medium: 0, low: 0, journal: 0 };
    const view = assembleAlarmView([alarm({ severity: "warning" })], { ...base, liveCounts: live });
    expect(view.counts.critical).toBe(9);
  });
});

describe("assembleAlarmView — Flood & Aufklappen", () => {
  const flood = Array.from({ length: 12 }, (_n, i) =>
    alarm({ id: i + 1, machine_id: 1, code: "OVERLOAD", severity: "alarm" }),
  );

  it("Flood → gebündelte Zeile statt 12 (eingeklappt)", () => {
    const view = assembleAlarmView(flood, base);
    const bundles = view.rows.filter((r) => r.kind === "bundle");
    const rows = view.rows.filter((r) => r.kind === "row");
    expect(bundles).toHaveLength(1);
    expect(rows).toHaveLength(0);
    expect(view.total).toBe(12); // total zählt die gebündelten Mitglieder
  });

  it("aufgeklapptes Bündel zeigt die Mitglieder zusätzlich", () => {
    const view = assembleAlarmView(flood, {
      ...base,
      expandedBundles: new Set(["line:3|OVERLOAD"]),
    });
    const rows = view.rows.filter((r) => r.kind === "row");
    expect(rows).toHaveLength(12);
  });
});

describe("assembleAlarmView — Filter & Scope", () => {
  it("Scope-Filter blendet fremde Maschinen aus (UX)", () => {
    const view = assembleAlarmView(
      [alarm({ machine_id: 1, severity: "alarm" }), alarm({ machine_id: 3, severity: "alarm" })],
      { ...base, visibleMachine: (id) => id === 1 },
    );
    expect(view.total).toBe(1);
  });

  it("Lebenszyklus-Filter 'open' verbirgt geklärte", () => {
    const view = assembleAlarmView(
      [alarm({ severity: "alarm" }), alarm({ severity: "alarm", cleared_at: "2026-06-17T09:00:00Z" })],
      base,
    );
    expect(view.total).toBe(1);
  });

  it("driftOnly zeigt nur Drift-Warnungen", () => {
    const view = assembleAlarmView(
      [alarm({ code: "DRIFT", severity: "warning" }), alarm({ code: null, severity: "alarm" })],
      { ...base, filter: { ...defaultFilter(), driftOnly: true } },
    );
    expect(view.total).toBe(1);
  });

  it("alle Gruppierungsmodi liefern eine konsistente Sicht", () => {
    for (const mode of GROUP_MODES) {
      const view = assembleAlarmView([alarm({ severity: "alarm" })], { ...base, groupMode: mode });
      expect(view.rows.some((r) => r.kind === "header")).toBe(true);
      expect(view.total).toBe(1);
    }
  });
});
