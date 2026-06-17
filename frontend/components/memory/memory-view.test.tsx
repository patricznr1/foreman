// ============================================================
//  FOREMAN Frontend — components/memory/memory-view.test.tsx
//  Zweck: On-Demand-Fluss der Gedächtnis-Suche — Trigger (Deep-Link) → benannter
//         Verarbeitungszustand → Ergebnis mit Herkunft; KEIN KI-Stempel (Retrieval);
//         keine Scheingenauigkeit; ehrlicher 503-Pfad; Offline-Degradation; Rollen.
// ============================================================
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CurrentUser } from "@/lib/api/contracts";
import { makeNote } from "@/lib/memory/testing/fixtures";
import { MemoryView } from "./memory-view";

function user(over: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: 1,
    email: "w@example.com",
    role: "worker",
    assigned_line_ids: [],
    assigned_machine_ids: [12],
    ...over,
  };
}

const NOTES = [
  makeNote({ id: 1, machine_id: 12, shift: "Früh", created_at: "2026-06-10T08:00:00+00:00" }),
  makeNote({
    id: 2,
    machine_id: 12,
    shift: "Spät",
    text: "Spindel auffällig laut.",
    author: null,
    created_at: "2026-06-11T08:00:00+00:00",
  }),
];

function mockFetch(notes: unknown): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => notes }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
});

describe("MemoryView (On-Demand)", () => {
  it("Deep-Link löst eine Suche aus → Ergebnis mit Herkunft, OHNE KI-Stempel, ohne Prozent", async () => {
    mockFetch(NOTES);
    render(<MemoryView user={user()} initialQuery="Lager heiß" />);
    await waitFor(() => expect(screen.getByText(/2 ähnliche Fälle gefunden/)).toBeInTheDocument());
    // Herkunftsstempel vorhanden (Stand) …
    expect(screen.getByText(/Gecacht/)).toBeInTheDocument();
    // … aber KEINE KI-Generierungs-Kennzeichnung (Abruf, keine Generierung) …
    expect(screen.queryByText("KI-erzeugt")).toBeNull();
    // … und keine Scheingenauigkeit.
    expect(document.body.textContent).not.toMatch(/%/);
  });

  it("benennt den Verarbeitungszustand (kein generischer Spinner)", async () => {
    let release: () => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValue(
        new Promise((resolve) => {
          release = () => resolve({ ok: true, status: 200, json: async () => NOTES });
        }),
      ),
    );
    render(<MemoryView user={user()} initialQuery="Lager" />);
    expect(await screen.findByText(/Suche nach ähnlichen Fällen/)).toBeInTheDocument();
    release();
    await waitFor(() => expect(screen.getByText(/2 ähnliche Fälle gefunden/)).toBeInTheDocument());
  });

  it("Such-Backend-Ausfall (503) wird ehrlich benannt, nicht verschleiert", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) }),
    );
    render(<MemoryView user={user()} initialQuery="Lager" />);
    expect(await screen.findByText(/Gedächtnis derzeit nicht erreichbar/)).toBeInTheDocument();
  });

  it("offline: neue Suche deaktiviert mit Grund (Degradation)", () => {
    Object.defineProperty(navigator, "onLine", { value: false, configurable: true });
    try {
      render(<MemoryView user={user()} />);
      expect(screen.getByRole("button", { name: "Ähnliche Fälle finden" })).toBeDisabled();
      expect(screen.getByText(/Offline/)).toBeInTheDocument();
    } finally {
      Object.defineProperty(navigator, "onLine", { value: true, configurable: true });
    }
  });

  it("Rollen: Werker ohne Verknüpfungs-Ansicht, Techniker mit", async () => {
    mockFetch(NOTES);
    const { unmount } = render(<MemoryView user={user({ role: "worker" })} initialQuery="x" />);
    await waitFor(() => expect(screen.getByText(/2 ähnliche Fälle gefunden/)).toBeInTheDocument());
    expect(screen.queryByText("Wie die Fälle zusammenhängen")).toBeNull();
    unmount();

    mockFetch(NOTES);
    render(<MemoryView user={user({ role: "technician" })} initialQuery="x" />);
    await waitFor(() => expect(screen.getByText("Wie die Fälle zusammenhängen")).toBeInTheDocument());
  });
});
