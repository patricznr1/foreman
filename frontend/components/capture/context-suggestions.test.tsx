// ============================================================
//  FOREMAN Frontend — components/capture/context-suggestions.test.tsx
//  Zweck: Sichert die dezente Brücke zu H als OPT-IN: kein passives Senden des
//         Entwurfstexts (Datenschutz), Treffer erst auf bewusste Geste, Abruf statt
//         KI-Generierung, wegklappbar, und Ruhe ohne Maschine/offline.
// ============================================================
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { makeNote } from "@/lib/memory/testing/fixtures";
import { ContextSuggestions } from "./context-suggestions";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubHits() {
  const mock = vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => [makeNote({ id: 1, text: "Lager heiß an der Spindel" })],
  }) as Response);
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("ContextSuggestions — Datensparsamkeit (Opt-in)", () => {
  it("sendet den Entwurfstext NICHT passiv — kein Request ohne bewusste Geste", () => {
    const mock = stubHits();
    render(<ContextSuggestions text="Müller meldet Lager heiß" machineId={5} enabled />);
    // Der rohe (potenziell unmaskierte) Text verlässt das Gerät NICHT beim Tippen.
    expect(mock).not.toHaveBeenCalled();
    // Stattdessen ein bewusster Anstoß.
    expect(screen.getByRole("button", { name: /Ähnliche Notizen an dieser Maschine ansehen/ })).toBeInTheDocument();
  });

  it("ruht ohne Maschine — kein Button, kein Request", () => {
    const mock = stubHits();
    render(<ContextSuggestions text="Lager läuft heiß" machineId={null} enabled />);
    expect(mock).not.toHaveBeenCalled();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("ruht offline/ohne Berechtigung (enabled=false)", () => {
    const mock = stubHits();
    render(<ContextSuggestions text="Lager läuft heiß" machineId={5} enabled={false} />);
    expect(mock).not.toHaveBeenCalled();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("ContextSuggestions — Treffer auf Anstoß", () => {
  it("zeigt nach Klick frühere Fälle dezent — als Abruf, NICHT als KI-Generierung", async () => {
    const mock = stubHits();
    render(<ContextSuggestions text="Lager läuft heiß" machineId={5} enabled />);
    await userEvent.click(screen.getByRole("button", { name: /Ähnliche Notizen/ }));
    await waitFor(() => expect(screen.getByText(/Frühere Notizen an dieser Maschine/)).toBeInTheDocument());
    expect(mock).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Lager heiß an der Spindel/)).toBeInTheDocument();
    // Retrieval, kein KI-Output → kein „KI-erzeugt"-Stempel.
    expect(screen.queryByText(/KI-erzeugt/)).toBeNull();
  });

  it("ist wegklappbar (Vorschlag, kein Pop-up-Zwang)", async () => {
    stubHits();
    render(<ContextSuggestions text="Lager läuft heiß" machineId={5} enabled />);
    await userEvent.click(screen.getByRole("button", { name: /Ähnliche Notizen/ }));
    await waitFor(() => expect(screen.getByText(/Frühere Notizen/)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /ausblenden/ }));
    expect(screen.queryByText(/Frühere Notizen/)).toBeNull();
  });
});
