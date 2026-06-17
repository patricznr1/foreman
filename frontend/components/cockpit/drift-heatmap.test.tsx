// ============================================================
//  FOREMAN Frontend — components/cockpit/drift-heatmap.test.tsx
//  Zweck: Sichert die verbindlichen Designvorgaben der DriftHeatmap (§4A/§5.2/§5.8):
//         Raster Klasse × Maschine, entsättigte sequenzielle Füllung OHNE Severity-
//         Farbe in der Fläche, Schraffur + FCSM-Buchstabe (Mehrkanal), Klick → B,
//         Tastatur-Navigation (Roving-Tabindex), Kipp-Puls, systematisches Klassen-
//         Drift-Muster, Mini-Vorschau.
// ============================================================
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MachineStatusOut } from "@/lib/api/contracts";
import { buildHeatmapMatrix } from "@/lib/cockpit/matrix";

import { DriftHeatmap } from "./drift-heatmap";

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

const MACHINES: MachineStatusOut[] = [
  machine({ id: 1, label: "Presse 1", machine_class: "Presse", status: "healthy" }),
  machine({ id: 2, label: "Presse 2", machine_class: "Presse", status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
  machine({ id: 3, label: "Spindel 1", machine_class: "Spindel", status: "open_warning", open_alarm_count: 2, open_by_severity: { critical: 1, warning: 1 } }),
];

function renderHeatmap(machines: MachineStatusOut[] = MACHINES, onSelect = vi.fn(), kipped?: Set<number>) {
  render(<DriftHeatmap matrix={buildHeatmapMatrix(machines)} onSelectCell={onSelect} kippedMachineIds={kipped} />);
  return { onSelect };
}

describe("DriftHeatmap", () => {
  it("rendert ein Raster (grid) mit Zeilen je Klasse und Zellen je Maschine", () => {
    renderHeatmap();
    expect(screen.getByRole("grid")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(2); // Presse, Spindel
    expect(screen.getAllByRole("gridcell")).toHaveLength(3);
  });

  it("füllt abweichende Zellen mit der sequenziellen Heatmap-Palette, ruhige mit der Grundfläche", () => {
    renderHeatmap();
    const healthy = screen.getByRole("gridcell", { name: /Presse 1/ });
    const drift = screen.getByRole("gridcell", { name: /Presse 2/ });
    expect(healthy.querySelector("rect")?.getAttribute("fill")).toBe("var(--color-surface-raised)");
    expect(drift.querySelector("rect")?.getAttribute("fill")).toBe("var(--color-heatmap-2)");
  });

  it("trägt KEINE Severity-Farbe in der Heatmap-Fläche (§4A)", () => {
    renderHeatmap();
    const grid = screen.getByRole("grid");
    expect(grid.innerHTML).not.toContain("color-alarm-");
    expect(grid.innerHTML).not.toContain("color-state-");
  });

  it("kodiert Richtung mehrkanalig: Schraffur (Pattern) + FCSM-Buchstabe je Zelle", () => {
    renderHeatmap();
    const grid = screen.getByRole("grid");
    expect(grid.querySelector("pattern")).not.toBeNull();
    const drift = screen.getByRole("gridcell", { name: /Presse 2/ });
    // Drift → Schraffur „over" + FCSM-Buchstabe S (drift_active → außer Spezifikation)
    const hatch = [...drift.querySelectorAll("rect")].some((r) => r.getAttribute("fill")?.includes("hatch-over"));
    expect(hatch).toBe(true);
    expect(drift.querySelector("text")?.textContent).toBe("S");
    // Normalbetrieb → kein Buchstabe (ruhige Zelle)
    expect(screen.getByRole("gridcell", { name: /Presse 1/ }).querySelector("text")).toBeNull();
  });

  it("klick auf eine Zelle ruft den Querlink-Handler (→ B) mit der Maschine auf", () => {
    const { onSelect } = renderHeatmap();
    fireEvent.click(screen.getByRole("gridcell", { name: /Spindel 1/ }));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0]![0]).toMatchObject({ machineId: 3, kind: "warning" });
  });

  it("ist tastaturnavigierbar (Roving-Tabindex): Pfeil-rechts verschiebt den Tab-Stop", () => {
    renderHeatmap();
    expect(screen.getByRole("gridcell", { name: /Presse 1/ }).getAttribute("tabindex")).toBe("0");
    fireEvent.keyDown(screen.getByRole("grid"), { key: "ArrowRight" });
    expect(screen.getByRole("gridcell", { name: /Presse 2/ }).getAttribute("tabindex")).toBe("0");
    expect(screen.getByRole("gridcell", { name: /Presse 1/ }).getAttribute("tabindex")).toBe("-1");
  });

  it("Enter auf der aktiven Zelle löst den Querlink aus", () => {
    const { onSelect } = renderHeatmap();
    fireEvent.keyDown(screen.getByRole("grid"), { key: "Enter" });
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0]![0]).toMatchObject({ machineId: 1 });
  });

  it("markiert systematische Drift einer Klasse (Mehrheit driftet)", () => {
    render(
      <DriftHeatmap
        matrix={buildHeatmapMatrix([
          machine({ id: 1, machine_class: "Presse", status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
          machine({ id: 2, machine_class: "Presse", status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
        ])}
      />,
    );
    expect(screen.getByRole("row", { name: /systematische Abweichung in der Klasse/ })).toBeInTheDocument();
  });

  it("pulst eine frisch gekippte Zelle einmalig (state-flip), nicht dauerhaft", () => {
    renderHeatmap(MACHINES, vi.fn(), new Set([2]));
    expect(screen.getByRole("gridcell", { name: /Presse 2/ }).classList.contains("state-flip")).toBe(true);
    expect(screen.getByRole("gridcell", { name: /Presse 1/ }).classList.contains("state-flip")).toBe(false);
  });

  it("zeigt eine Mini-Vorschau der angetippten Zelle (höfliche Live-Region)", () => {
    renderHeatmap();
    fireEvent.click(screen.getByRole("gridcell", { name: /Presse 2/ })); // Drift, nicht kritisch
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Presse 2");
  });

  it("kritische Zelle → assertive Live-Region (§5.8 höflich/assertiv je Priorität)", () => {
    renderHeatmap();
    fireEvent.click(screen.getByRole("gridcell", { name: /Spindel 1/ })); // offener kritischer Alarm
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Spindel 1");
    expect(alert).toHaveTextContent("2 offene Alarme");
  });

  it("leerer Geltungsbereich → ruhiger Hinweis statt kaputter Fläche", () => {
    render(<DriftHeatmap matrix={buildHeatmapMatrix([])} />);
    expect(screen.getByRole("status")).toHaveTextContent("Keine Maschinen im Geltungsbereich");
  });
});
