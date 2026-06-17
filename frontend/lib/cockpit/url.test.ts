// ============================================================
//  FOREMAN Frontend — lib/cockpit/url.test.ts
//  Zweck: Sichert die realen Querlink-Ziele (B/C/E) und die Scope-URLs.
// ============================================================
import { describe, expect, it } from "vitest";

import { alarmsHref, machineHref, predictionHref, scopeHref } from "./url";

describe("Querlink-Ziele", () => {
  it("Zelle → Maschinen-Detail (B)", () => {
    expect(machineHref(7)).toBe("/machines/7");
  });

  it("Prioritätsspalte → Alarme (C)", () => {
    expect(alarmsHref()).toBe("/alarms");
  });

  it("Drift → Ausfallvorhersage der Maschine (E)", () => {
    expect(predictionHref(7)).toBe("/insights/prediction?machine=7");
  });
});

describe("scopeHref", () => {
  it("Flotte (kein Filter) → /overview ohne Query", () => {
    expect(scopeHref({ machineClass: null, lineId: null })).toBe("/overview");
  });

  it("nur Klasse", () => {
    expect(scopeHref({ machineClass: "Presse", lineId: null })).toBe("/overview?class=Presse");
  });

  it("Klasse + Linie", () => {
    expect(scopeHref({ machineClass: "Presse", lineId: 2 })).toBe("/overview?class=Presse&line=2");
  });
});
