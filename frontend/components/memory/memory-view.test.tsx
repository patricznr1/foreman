// ============================================================
//  FOREMAN Frontend — components/memory/memory-view.test.tsx
//  Zweck: On-Demand-Fluss des ARCHIVS (Paket 1c) — ehrliche Umwidmung (Titel
//         „Archiv", kein „Hatten wir das schon mal"), konsumiert /archive/search,
//         Treffer mit Herkunft (KEIN KI-Stempel, keine Scheingenauigkeit), drei
//         Quellen korrekt typisiert, KEINE Verdichtung/Verknüpfung, Quellen-Toggles
//         steuern sources[], 503 ohne Sonderpfad (generisch), Offline-Degradation.
// ============================================================
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CurrentUser } from "@/lib/api/contracts";
import { makeArchiveHit } from "@/lib/memory/testing/fixtures";
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

const HITS = [
  makeArchiveHit({ source_type: "note", id: 1, machine_id: 12, detail: { shift: "Früh" } }),
  makeArchiveHit({
    source_type: "maintenance",
    id: 2,
    machine_id: 12,
    excerpt: "Schmierung erneuert.",
    detail: { type: "lubrication" },
  }),
  makeArchiveHit({
    source_type: "alarm",
    id: 3,
    machine_id: 12,
    excerpt: "Beleuchtung defekt.",
    detail: { severity: "warning", category: "process", code: "ILL-7" },
  }),
];

function mockFetch(hits: unknown): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => hits });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
});

describe("Archiv (MemoryView, On-Demand)", () => {
  it("ist ehrlich als 'Archiv' benannt — kein 'Hatten wir das schon mal'", () => {
    mockFetch([]);
    render(<MemoryView user={user()} />);
    expect(screen.getByRole("heading", { level: 1, name: "Archiv" })).toBeInTheDocument();
    expect(screen.getByText(/Wartungsprotokolle und Alarme im Wortlaut/)).toBeInTheDocument();
    expect(screen.queryByText(/Hatten wir das schon mal/)).toBeNull();
  });

  it("Deep-Link löst eine Suche über /archive/search aus → Treffer mit Herkunft, ohne KI-Stempel, ohne Prozent", async () => {
    const fetchMock = mockFetch(HITS);
    render(<MemoryView user={user()} initialQuery="Fett" />);
    await waitFor(() => expect(screen.getByText(/3 Treffer im Archiv/)).toBeInTheDocument());
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/v1/archive/search");
    expect(screen.getByText(/Gecacht/)).toBeInTheDocument();
    expect(screen.queryByText("KI-erzeugt")).toBeNull();
    expect(document.body.textContent).not.toMatch(/%/);
  });

  it("typisiert die drei Quellen korrekt und rendert KEINE Verdichtung/Verknüpfung", async () => {
    mockFetch(HITS);
    render(<MemoryView user={user({ role: "technician" })} initialQuery="Fett" />);
    await waitFor(() => expect(screen.getByText(/3 Treffer im Archiv/)).toBeInTheDocument());
    expect(screen.getByLabelText("Schichtnotiz, Maschine 12")).toBeInTheDocument();
    expect(screen.getByLabelText("Wartung, Maschine 12")).toBeInTheDocument();
    expect(screen.getByLabelText("Alarm, Maschine 12")).toBeInTheDocument();
    // assoziative Sicht (relation-view) NICHT gerendert
    expect(screen.queryByText(/zusammenhängen/)).toBeNull();
  });

  it("benennt den Verarbeitungszustand (kein generischer Spinner)", async () => {
    let release: () => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValue(
        new Promise((resolve) => {
          release = () => resolve({ ok: true, status: 200, json: async () => HITS });
        }),
      ),
    );
    render(<MemoryView user={user()} initialQuery="Fett" />);
    expect(await screen.findByText(/Durchsucht das Archiv/)).toBeInTheDocument();
    release();
    await waitFor(() => expect(screen.getByText(/3 Treffer im Archiv/)).toBeInTheDocument());
  });

  it("Quellen-Toggle: Wartung deaktivieren entfernt maintenance aus dem Request", async () => {
    const fetchMock = mockFetch(HITS);
    render(<MemoryView user={user({ role: "technician" })} initialQuery="Fett" />);
    await waitFor(() => expect(screen.getByText(/3 Treffer im Archiv/)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Wartung" }));
    await userEvent.click(screen.getByRole("button", { name: "Suchen" }));
    const lastUrl = String(fetchMock.mock.calls.at(-1)?.[0]);
    expect(lastUrl).toContain("sources=note%2Calarm");
    expect(lastUrl).not.toContain("maintenance");
  });

  it("Backend-Ausfall (503) wird generisch benannt — kein 503-Sonderpfad mehr", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) }),
    );
    render(<MemoryView user={user()} initialQuery="Fett" />);
    expect(await screen.findByText(/Suche nicht möglich/)).toBeInTheDocument();
    expect(screen.queryByText(/Gedächtnis derzeit nicht erreichbar/)).toBeNull();
  });

  it("offline: neue Suche deaktiviert mit Grund (Degradation)", () => {
    Object.defineProperty(navigator, "onLine", { value: false, configurable: true });
    try {
      render(<MemoryView user={user()} />);
      expect(screen.getByRole("button", { name: "Suchen" })).toBeDisabled();
      expect(screen.getByText(/Offline/)).toBeInTheDocument();
    } finally {
      Object.defineProperty(navigator, "onLine", { value: true, configurable: true });
    }
  });
});
