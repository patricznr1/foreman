// ============================================================
//  FOREMAN Frontend — components/capture/hidden-term.test.tsx
//  Zweck: Hidden-Term-Gate für Sektion J (GROUND_TRUTH §17 III, Studie §4J). Die
//         Erfassung — inkl. der Brücke zu H (Kontextvorschlag) — erscheint
//         AUSSCHLIESSLICH in Hallensprache: kein internes Verfahrens-/Bibliotheks-/
//         Substrat-Vokabular, keine Scheingenauigkeit (kein „%"). Render-basierter
//         Scan über den sichtbaren DOM-Text (wie components/memory/hidden-term).
// ============================================================
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { captureRoleView } from "@/lib/capture/roles";
import { makeMachine, makeUser } from "@/lib/capture/testing/fixtures";
import { makeNote } from "@/lib/memory/testing/fixtures";
import type { MachinesState } from "@/lib/capture/use-machines";
import { CaptureForm } from "./capture-form";
import { ContextSuggestions } from "./context-suggestions";

const FORBIDDEN = [
  "embedding",
  "vektor",
  "vector",
  "cosine",
  "kosinus",
  "hnsw",
  "pgvector",
  "bge-m3",
  "ollama",
  "presidio",
  "vektorsuche",
  "semantisch",
  "substrat",
  "neuronal",
  "ähnlichkeitssuche",
];

const READY: MachinesState = { kind: "ready", machines: [makeMachine({ id: 2, label: "Drehbank 2" })] };

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("Hidden-Term-Scan (Sektion J)", () => {
  it("das Erfassungs-Formular nutzt nur Hallensprache (kein internes Vokabular)", () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, json: async () => [] }) as Response));
    render(
      <CaptureForm
        user={makeUser({ role: "worker", assigned_machine_ids: [2] })}
        roleView={captureRoleView("worker")}
        machinesState={READY}
        initialMachineId={2}
      />,
    );
    const text = (document.body.textContent ?? "").toLowerCase();
    for (const term of FORBIDDEN) {
      expect(text.includes(term)).toBe(false);
    }
    // Keine Scheingenauigkeit (das Such-Backend liefert keinen Score).
    expect(document.body.textContent).not.toMatch(/%/);
  });

  it("auch der Kontextvorschlag (Brücke zu H) bleibt in Hallensprache", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => [makeNote({ id: 1, text: "Lager heiß, Späne bläulich" })],
      }) as Response),
    );
    render(<ContextSuggestions text="Lager läuft heiß" machineId={2} enabled />);
    await userEvent.click(screen.getByRole("button", { name: /Ähnliche Notizen/ }));
    await waitFor(() => expect(screen.getByText(/Frühere Notizen/)).toBeInTheDocument(), {
      timeout: 2000,
    });
    const text = (document.body.textContent ?? "").toLowerCase();
    for (const term of FORBIDDEN) {
      expect(text.includes(term)).toBe(false);
    }
    expect(document.body.textContent).not.toMatch(/%/);
  });
});
