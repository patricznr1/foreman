// ============================================================
//  FOREMAN Frontend — components/capture/machine-select.test.tsx
//  Zweck: Sichert die Maschinen-Auswahl-Chips inkl. der fünf Pflichtzustände
//         (lädt/bereit/leer/Fehler) und der „Allgemein"-Option (machine_id null).
// ============================================================
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { makeMachine } from "@/lib/capture/testing/fixtures";
import { MachineSelect } from "./machine-select";

describe("MachineSelect — Zustände", () => {
  it("zeigt einen Lade-Hinweis (role=status)", () => {
    render(<MachineSelect state={{ kind: "loading" }} value={null} onChange={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent(/geladen/);
  });

  it("bleibt bei leerem Scope erfassbar (ohne Maschinenbezug)", () => {
    render(<MachineSelect state={{ kind: "empty" }} value={null} onChange={() => {}} />);
    expect(screen.getByText(/ohne Maschinenbezug/)).toBeInTheDocument();
  });

  it("bleibt bei Listen-Fehler erfassbar (degradiert, kein Alarm)", () => {
    render(<MachineSelect state={{ kind: "error" }} value={null} onChange={() => {}} />);
    expect(screen.getByText(/nicht abrufbar/)).toBeInTheDocument();
  });
});

describe("MachineSelect — Auswahl", () => {
  const machines = [makeMachine({ id: 1, label: "Drehbank 1" }), makeMachine({ id: 2, label: "Fräse 2" })];

  it("zeigt 'Allgemein' plus die wählbaren Maschinen als Chips", () => {
    render(<MachineSelect state={{ kind: "ready", machines }} value={null} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Allgemein" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Drehbank 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fräse 2" })).toBeInTheDocument();
  });

  it("meldet die gewählte Maschine bzw. 'Allgemein' (null)", async () => {
    const onChange = vi.fn();
    render(<MachineSelect state={{ kind: "ready", machines }} value={2} onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Fräse 2" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Drehbank 1" }));
    expect(onChange).toHaveBeenCalledWith(1);
    await userEvent.click(screen.getByRole("button", { name: "Allgemein" }));
    expect(onChange).toHaveBeenCalledWith(null);
  });
});
