// ============================================================
//  FOREMAN Frontend — lib/cockpit/kpis.test.ts
//  Zweck: Sichert die KPI-Aggregate (über den Scope, nicht flottenweit) und die
//         ruhigen Zustands-Rampen (KpiTile nie nackt, Severity nur in der KPI-Zeile).
// ============================================================
import { describe, expect, it } from "vitest";

import type { MachineStatusOut } from "@/lib/api/contracts";

import {
  availabilityFcsm,
  buildCockpitKpis,
  criticalFcsm,
  driftFcsm,
} from "./kpis";

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

describe("buildCockpitKpis", () => {
  it("zählt gesund/abweichend/Drift und summiert Alarme + kritische", () => {
    const kpis = buildCockpitKpis([
      machine({ id: 1, status: "healthy" }),
      machine({ id: 2, status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
      machine({ id: 3, status: "open_warning", open_alarm_count: 2, open_by_severity: { critical: 1, warning: 1 } }),
    ]);
    expect(kpis.total).toBe(3);
    expect(kpis.healthy).toBe(1);
    expect(kpis.deviating).toBe(2); // Drift + offene Warnung
    expect(kpis.driftCount).toBe(1);
    expect(kpis.openAlarmTotal).toBe(3);
    expect(kpis.criticalOpen).toBe(1);
    expect(kpis.availabilityPct).toBe(33); // round(1/3*100)
  });

  it("leere Flotte → 100 % Verfügbarkeit (nichts auffällig, kein NaN)", () => {
    const kpis = buildCockpitKpis([]);
    expect(kpis.availabilityPct).toBe(100);
    expect(kpis.total).toBe(0);
  });
});

describe("Zustands-Rampen", () => {
  it("Verfügbarkeit: hoch ok, mittel außer Spezifikation, niedrig Funktionsprüfung", () => {
    expect(availabilityFcsm(100)).toBe("ok");
    expect(availabilityFcsm(95)).toBe("ok");
    expect(availabilityFcsm(85)).toBe("outofspec");
    expect(availabilityFcsm(50)).toBe("check");
  });

  it("Drift-Zähler: 0 ok, sonst außer Spezifikation (kein Alarm-Rot)", () => {
    expect(driftFcsm(0)).toBe("ok");
    expect(driftFcsm(2)).toBe("outofspec");
  });

  it("kritische Alarme: 0 ok, sonst Ausfall (die eine dominante Severity)", () => {
    expect(criticalFcsm(0)).toBe("ok");
    expect(criticalFcsm(1)).toBe("failure");
  });
});
