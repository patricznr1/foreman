// ============================================================
//  FOREMAN Frontend — components/cockpit/cockpit-kpi-row.test.tsx
//  Zweck: Sichert die KPI-Zeile (§4A): drei KpiTiles aus den Aggregaten (nie nackt),
//         antippbare Kennzahlen ins Drill-down (→ Alarme C).
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CockpitKpis } from "@/lib/cockpit/kpis";

import { CockpitKpiRow, type KpiHistory } from "./cockpit-kpi-row";

const KPIS: CockpitKpis = {
  total: 10,
  healthy: 8,
  deviating: 2,
  availabilityPct: 80,
  driftCount: 1,
  openAlarmTotal: 3,
  criticalOpen: 1,
};

const HISTORY: KpiHistory = {
  availability: [90, 85, 80],
  criticalOpen: [0, 1, 1],
  driftCount: [0, 0, 1],
};

describe("CockpitKpiRow", () => {
  it("zeigt die drei Kennzahlen mit Wert und Zustand (nie nackt)", () => {
    render(<CockpitKpiRow kpis={KPIS} history={HISTORY} />);
    expect(screen.getByText("Flottenverfügbarkeit")).toBeInTheDocument();
    expect(screen.getByText("80")).toBeInTheDocument();
    expect(screen.getByText("Offene kritische Alarme")).toBeInTheDocument();
    expect(screen.getByText("Maschinen in Abweichung")).toBeInTheDocument();
  });

  it("verlinkt offene kritische Alarme und Abweichungen ins Drill-down (→ C)", () => {
    render(<CockpitKpiRow kpis={KPIS} history={HISTORY} />);
    const critical = screen.getByRole("link", { name: /Offene kritische Alarme ansehen/ });
    expect(critical).toHaveAttribute("href", "/alarms");
    const drift = screen.getByRole("link", { name: /Maschinen in Abweichung ansehen/ });
    expect(drift).toHaveAttribute("href", "/alarms");
  });

  it("rendert die Verlaufs-Sparklines (Mehrkanal, Prinzip 6)", () => {
    const { container } = render(<CockpitKpiRow kpis={KPIS} history={HISTORY} />);
    // drei KpiTiles mit je einer Spark-Polyline (history.length > 1)
    expect(container.querySelectorAll("polyline").length).toBe(3);
  });
});
