// ============================================================
//  FOREMAN Frontend — components/memory/search-result-card.test.tsx
//  Zweck: Treffer-Karte — Relevanz als Stärke/Position (KEIN Prozent), Autor
//         maskiert (#hex6, kein Klartext), Querlinks B/D graceful, keine erfundene
//         Auflösung.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { memoryRoleView } from "@/lib/memory/roles";
import { makeNote } from "@/lib/memory/testing/fixtures";
import { assembleSearchResult } from "@/lib/memory/view-model";
import { SearchResultCard } from "./search-result-card";

function firstHit(over: Parameters<typeof makeNote>[0] = {}) {
  const [hit] = assembleSearchResult([makeNote(over)], "x").hits;
  if (!hit) {
    throw new Error("Fixture lieferte keinen Treffer");
  }
  return hit;
}

describe("SearchResultCard", () => {
  it("zeigt Relevanz als Stärke + Position, niemals als Prozent", () => {
    render(<SearchResultCard hit={firstHit()} total={5} roleView={memoryRoleView("technician")} />);
    expect(screen.getByText(/Rang 1 von 5/)).toBeInTheDocument();
    expect(screen.getByText(/starke Nähe/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/%/);
  });

  it("maskiert den Autor (#hex6) und zeigt nie das rohe Token", () => {
    const token = "v1:a3f9d8e2c1b40000000000000000000000000000000000000000000000000000";
    render(<SearchResultCard hit={firstHit({ author: token })} total={1} roleView={memoryRoleView("worker")} />);
    expect(screen.getByText("#a3f9d8")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(token);
    expect(document.body.textContent).not.toContain("v1:");
  });

  it("verlinkt zur Maschine (B) und markiert die Ereigniskette (D) graceful", () => {
    render(<SearchResultCard hit={firstHit({ machine_id: 12 })} total={1} roleView={memoryRoleView("technician")} />);
    expect(screen.getByRole("link", { name: "An Maschine ansehen" })).toHaveAttribute("href", "/machines/12");
    expect(screen.getByText(/Ereigniskette rekonstruieren \(folgt\)/)).toBeInTheDocument();
  });

  it("erfindet keine Auflösung, wenn keine bekannt ist", () => {
    render(<SearchResultCard hit={firstHit()} total={1} roleView={memoryRoleView("technician")} />);
    expect(screen.queryByText(/Gelöst durch/)).toBeNull();
  });
});
