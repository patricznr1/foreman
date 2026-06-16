// ============================================================
//  FOREMAN Frontend — lib/ui/five-states.test.tsx
//  Zweck: Die Fünf-Zustände-Hülle stellt alle Zustände korrekt dar — und die
//         Degradation friert ein: "gecacht" zeigt die letzten Daten weiter
//         (kein weißer Screen), markiert über die Frische "cached".
//  Architektur-Einordnung: Quality-Gate (Akzeptanzkriterium Fünf-Zustände).
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DataState } from "@/lib/state/view-state";
import { FiveState } from "./five-states";

function renderContent(state: DataState<{ v: number }>) {
  return render(
    <FiveState state={state} label="Übersicht">
      {(data, freshness) => (
        <div data-testid="content" data-freshness={freshness}>
          {data.v}
        </div>
      )}
    </FiveState>,
  );
}

describe("FiveState — fünf Pflichtzustände", () => {
  it("lädt → Live-Region (aria-busy)", () => {
    renderContent({ kind: "loading" });
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
  });

  it("Fehler → alert in Hallensprache", () => {
    renderContent({ kind: "error", message: "forbidden" });
    expect(screen.getByRole("alert")).toHaveTextContent("Kein Zugriff");
  });

  it("leer → Hinweis statt leerem Screen", () => {
    renderContent({ kind: "empty" });
    expect(screen.getByRole("status")).toHaveTextContent(/keine Daten/i);
  });

  it("live → Inhalt mit Frische 'live'", () => {
    renderContent({ kind: "live", data: { v: 7 } });
    const content = screen.getByTestId("content");
    expect(content).toHaveTextContent("7");
    expect(content).toHaveAttribute("data-freshness", "live");
  });

  it("gecacht → Degradation friert ein: Inhalt bleibt, Frische 'cached'", () => {
    renderContent({ kind: "cached", data: { v: 7 } });
    const content = screen.getByTestId("content");
    expect(content).toHaveTextContent("7"); // NICHT leer
    expect(content).toHaveAttribute("data-freshness", "cached");
  });
});
