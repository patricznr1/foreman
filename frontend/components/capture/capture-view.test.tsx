// ============================================================
//  FOREMAN Frontend — components/capture/capture-view.test.tsx
//  Zweck: Sichert den Rollen-Split: erfassende Rollen bekommen das Formular, der
//         Manager (liest, erfasst nicht) eine reduzierte Lese-/Hinweis-Ansicht.
// ============================================================
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { makeUser } from "@/lib/capture/testing/fixtures";
import { CaptureView } from "./capture-view";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubMachines() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => [] }) as Response),
  );
}

describe("CaptureView — Rollen", () => {
  it("zeigt dem Werker das Erfassungs-Formular (Kernnutzer)", () => {
    stubMachines();
    render(<CaptureView user={makeUser({ role: "worker" })} initialMachineId={null} />);
    expect(screen.getByLabelText(/Was hast du beobachtet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Notiz speichern/ })).toBeInTheDocument();
  });

  it("zeigt dem Manager KEIN Formular, sondern den Lese-Hinweis + Sprung ins Gedächtnis", () => {
    stubMachines();
    render(<CaptureView user={makeUser({ role: "manager" })} initialMachineId={null} />);
    expect(screen.queryByLabelText(/Was hast du beobachtet/)).toBeNull();
    expect(screen.queryByRole("button", { name: /Notiz speichern/ })).toBeNull();
    expect(screen.getByRole("link", { name: /Gedächtnis/ })).toHaveAttribute("href", "/memory");
  });
});
