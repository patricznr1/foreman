// ============================================================
//  FOREMAN Frontend — components/event-chains/saved-chains-list.test.tsx
//  Zweck: Fünf Pflichtzustände der gespeicherten Ketten (lädt/gecacht/leer/Fehler).
// ============================================================
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeRead } from "@/lib/event-chains/testing/fixtures";
import { SavedChainsList } from "./saved-chains-list";

function res(ok: boolean, status: number, data: unknown): Response {
  return { ok, status, json: async () => data } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("SavedChainsList — fünf Zustände", () => {
  it("lädt → Live-Region (aria-busy)", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    render(<SavedChainsList machineId={null} selectedId={null} onOpen={() => {}} />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
  });

  it("leer → Hinweis statt leerem Screen", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(true, 200, [])));
    render(<SavedChainsList machineId={null} selectedId={null} onOpen={() => {}} />);
    expect(await screen.findByText(/Noch keine Kette gespeichert/)).toBeInTheDocument();
  });

  it("gecacht → Listeneintrag mit Anker + Konfidenz", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(true, 200, [makeRead()])));
    render(<SavedChainsList machineId={7} selectedId={null} onOpen={() => {}} />);
    expect(await screen.findByText(/Alarm #1/)).toBeInTheDocument();
    expect(screen.getByText(/hohe Konfidenz/)).toBeInTheDocument();
  });

  it("Fehler 403 → Hallensprache (kein Zugriff)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(false, 403, {})));
    render(<SavedChainsList machineId={null} selectedId={null} onOpen={() => {}} />);
    expect(await screen.findByText(/Kein Zugriff/)).toBeInTheDocument();
  });
});
