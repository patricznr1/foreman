// ============================================================
//  FOREMAN Frontend — lib/alarms/view-model.test.ts
//  Zweck: Bau des Zeilen-Modells — Priorität, Lebenszyklus, Puls (nur unquittiert-
//         kritisch), Shelving-Überlagerung, NE-107-Klasse, PII-Maskierung, Neu-Flag.
// ============================================================
import { describe, expect, it } from "vitest";
import { NOW, alarm, machines, noNew, noShelf } from "./testing/fixtures";
import { buildAlarmViewModel } from "./view-model";

const ctx = (over = {}) => ({ machines, shelf: noShelf, now: NOW, newIds: noNew, ...over });

describe("buildAlarmViewModel — Eskalations-Achsen", () => {
  it("kritisch + aktiv → 1-Hz-Puls an", () => {
    const vm = buildAlarmViewModel(alarm({ severity: "critical" }), ctx());
    expect(vm.priority).toBe("critical");
    expect(vm.pulse).toBe(true);
  });

  it("Quittieren stoppt den Puls, Priorität/Farbe bleiben", () => {
    const vm = buildAlarmViewModel(
      alarm({ severity: "critical", acknowledged_at: "2026-06-17T08:30:00Z" }),
      ctx(),
    );
    expect(vm.lifecycle).toBe("acknowledged");
    expect(vm.pulse).toBe(false);
    expect(vm.priority).toBe("critical"); // Farbe bleibt bis geklärt
  });

  it("nicht-kritisch pulst nie (ISA-18.2: Blinken=unquittiert, nicht Severity)", () => {
    expect(buildAlarmViewModel(alarm({ severity: "alarm" }), ctx()).pulse).toBe(false);
    expect(buildAlarmViewModel(alarm({ severity: "warning" }), ctx()).pulse).toBe(false);
  });

  it("Shelving überlagert aktiv → zurückgestellt, Puls aus (sichtbar, zeitbegrenzt)", () => {
    const a = alarm({ id: 77, severity: "critical" });
    const shelf = new Map([[77, NOW + 60_000]]);
    const vm = buildAlarmViewModel(a, ctx({ shelf }));
    expect(vm.lifecycle).toBe("shelved");
    expect(vm.shelvedUntil).toBe(NOW + 60_000);
    expect(vm.pulse).toBe(false);
  });

  it("abgelaufene Zurückstellung verfällt → wieder aktiv", () => {
    const a = alarm({ id: 77, severity: "critical" });
    const shelf = new Map([[77, NOW - 1]]);
    const vm = buildAlarmViewModel(a, ctx({ shelf }));
    expect(vm.lifecycle).toBe("active");
    expect(vm.pulse).toBe(true);
  });

  it("Drift → eigene Klasse, NE-107 'außerhalb Spezifikation' (S)", () => {
    const vm = buildAlarmViewModel(alarm({ code: "DRIFT", severity: "warning" }), ctx());
    expect(vm.isDrift).toBe(true);
    expect(vm.fcsm).toBe("outofspec");
  });

  it("Maschinen-Label/Linie aus Stammdaten, Fallback bei Unbekannt", () => {
    expect(buildAlarmViewModel(alarm({ machine_id: 1 }), ctx()).machineLabel).toBe("Presse 1");
    expect(buildAlarmViewModel(alarm({ machine_id: 1 }), ctx()).lineLabel).toBe("Linie 3");
    expect(buildAlarmViewModel(alarm({ machine_id: 999 }), ctx()).machineLabel).toBe(
      "Maschine 999",
    );
  });

  it("acknowledged_by erscheint nur maskiert (kein Klartext, §8)", () => {
    const vm = buildAlarmViewModel(
      alarm({ acknowledged_at: "2026-06-17T08:30:00Z", acknowledged_by: "v1:a7f3e8c2b9" }),
      ctx(),
    );
    expect(vm.acknowledgedByMasked).toBe("#a7f3e8");
  });

  it("Neu-Flag aus newIds (für den Einblend-Puls)", () => {
    const a = alarm({ id: 5 });
    expect(buildAlarmViewModel(a, ctx({ newIds: new Set([5]) })).isNew).toBe(true);
    expect(buildAlarmViewModel(a, ctx({ newIds: new Set([9]) })).isNew).toBe(false);
  });
});
