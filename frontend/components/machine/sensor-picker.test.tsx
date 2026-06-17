// ============================================================
//  FOREMAN Frontend — components/machine/sensor-picker.test.tsx
//  Zweck: Sichert die Sensorauswahl (ein-/ausblenden) für den Mehrfach-Sensor-Trend.
// ============================================================
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { DataPointRead } from "@/lib/api/contracts";

import { SensorPicker } from "./sensor-picker";

function dp(id: number, name: string): DataPointRead {
  return {
    id,
    machine_id: 7,
    component_id: null,
    name,
    kind: "analog",
    measurement_type: null,
    unit: "°C",
    source: "simulation",
    address: null,
    normal_min: null,
    normal_max: null,
    created_at: "2026-06-01T00:00:00Z",
  };
}

describe("SensorPicker", () => {
  it("listet Sensoren, markiert ausgewählte und schaltet um", () => {
    const onToggle = vi.fn();
    render(
      <SensorPicker dataPoints={[dp(42, "spindle_temp"), dp(43, "pressure")]} selected={[42]} onToggle={onToggle} />,
    );
    expect(screen.getByRole("button", { name: /spindle_temp/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /pressure/ })).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByRole("button", { name: /pressure/ }));
    expect(onToggle).toHaveBeenCalledWith(43);
  });
});
