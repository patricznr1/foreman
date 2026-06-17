// ============================================================
//  FOREMAN Frontend — lib/cockpit/scope.test.ts
//  Zweck: Sichert die Föderations-Achse als Client-Filter: Parsen, Filtern,
//         Breadcrumb-Pfad (Flotte ▸ Klasse ▸ Linie).
// ============================================================
import { describe, expect, it } from "vitest";

import type { MachineStatusOut } from "@/lib/api/contracts";

import { filterByScope, isScoped, parseScope, scopeCrumbs } from "./scope";

function machine(over: Partial<MachineStatusOut> = {}): MachineStatusOut {
  return {
    id: 1,
    label: "M",
    line_id: 1,
    machine_class: "Presse",
    status: "healthy",
    open_alarm_count: 0,
    open_by_severity: {},
    last_alarm_at: null,
    ...over,
  };
}

describe("parseScope", () => {
  it("liest Klasse und Linie aus den Query-Werten", () => {
    expect(parseScope({ class: "Presse", line: "3" })).toEqual({ machineClass: "Presse", lineId: 3 });
  });

  it("leere/ungültige Werte → Flotte (null)", () => {
    expect(parseScope({ class: "", line: "abc" })).toEqual({ machineClass: null, lineId: null });
    expect(parseScope({})).toEqual({ machineClass: null, lineId: null });
  });

  it("nur strikte Ganzzahlen sind gültige Linien-IDs (kein nachsichtiges parseInt)", () => {
    expect(parseScope({ line: "3abc" })).toEqual({ machineClass: null, lineId: null });
    expect(parseScope({ line: "2.5" })).toEqual({ machineClass: null, lineId: null });
    expect(parseScope({ line: " 7 " })).toEqual({ machineClass: null, lineId: 7 }); // getrimmt
  });

  it("nimmt bei Array-Parametern den ersten Wert", () => {
    expect(parseScope({ class: ["Spindel", "Presse"], line: ["5"] })).toEqual({
      machineClass: "Spindel",
      lineId: 5,
    });
  });
});

describe("filterByScope", () => {
  const machines = [
    machine({ id: 1, machine_class: "Presse", line_id: 1 }),
    machine({ id: 2, machine_class: "Spindel", line_id: 1 }),
    machine({ id: 3, machine_class: "Presse", line_id: 2 }),
  ];

  it("Flotte (null) → alle", () => {
    expect(filterByScope(machines, { machineClass: null, lineId: null })).toHaveLength(3);
  });

  it("filtert nach Klasse", () => {
    const r = filterByScope(machines, { machineClass: "Presse", lineId: null });
    expect(r.map((m) => m.id)).toEqual([1, 3]);
  });

  it("filtert nach Klasse UND Linie", () => {
    const r = filterByScope(machines, { machineClass: "Presse", lineId: 2 });
    expect(r.map((m) => m.id)).toEqual([3]);
  });
});

describe("isScoped", () => {
  it("erkennt eingeengten Geltungsbereich", () => {
    expect(isScoped({ machineClass: null, lineId: null })).toBe(false);
    expect(isScoped({ machineClass: "Presse", lineId: null })).toBe(true);
    expect(isScoped({ machineClass: null, lineId: 2 })).toBe(true);
  });
});

describe("scopeCrumbs", () => {
  it("Flotte allein → ein Krümel", () => {
    const crumbs = scopeCrumbs({ machineClass: null, lineId: null });
    expect(crumbs).toEqual([{ label: "Flotte", href: "/overview" }]);
  });

  it("Klasse + Linie → vollständiger Pfad mit deep-linkbaren hrefs", () => {
    const crumbs = scopeCrumbs({ machineClass: "Presse", lineId: 2 });
    expect(crumbs.map((c) => c.label)).toEqual(["Flotte", "Klasse: Presse", "Linie 2"]);
    expect(crumbs[1]!.href).toBe("/overview?class=Presse"); // Klasse droppt die Linie
    expect(crumbs[2]!.href).toBe("/overview?class=Presse&line=2");
  });
});
