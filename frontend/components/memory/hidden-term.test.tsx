// ============================================================
//  FOREMAN Frontend — components/memory/hidden-term.test.tsx
//  Zweck: STRENGSTES Gate der Serie (Studie §0/§1.3/§4H, GROUND_TRUTH §17 III):
//         im sichtbaren UI der Gedächtnis-Suche erscheint KEIN interner
//         Verfahrens-/Bibliotheks-/Substrat-Name — die Fähigkeit spricht reine
//         Hallensprache ("ähnliche Fälle", "Nähe", "Verknüpfung"). Zusätzlich:
//         keine Scheingenauigkeit (kein Prozentzeichen).
// ============================================================
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { memoryRoleView } from "@/lib/memory/roles";
import { makeNote } from "@/lib/memory/testing/fixtures";
import { assembleSearchResult } from "@/lib/memory/view-model";
import { MemoryResultList } from "./memory-result-list";
import { MemorySearchBar } from "./memory-search-bar";

// Interne Begriffe aus dem Innenleben des Gedächtnisses (F-SEM) — nie sichtbar.
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

describe("Hidden-Term-Scan (strengstes Gate)", () => {
  it("kein interner Verfahrensbegriff erscheint im sichtbaren Output", () => {
    const result = assembleSearchResult(
      [
        makeNote({ id: 1, machine_id: 7, shift: "Früh" }),
        makeNote({ id: 2, machine_id: 7, shift: "Früh" }),
        makeNote({ id: 3, machine_id: 9, shift: "Spät", text: "Vibration an der Spindel.", author: null }),
      ],
      "Lager läuft heiß",
    );
    render(
      <>
        <MemorySearchBar onSubmit={() => {}} busy={false} canFilter machines={[7, 9]} />
        <MemoryResultList result={result} roleView={memoryRoleView("technician")} announce />
      </>,
    );
    const text = (document.body.textContent ?? "").toLowerCase();
    for (const term of FORBIDDEN) {
      expect(text.includes(term), `verbotener Begriff im sichtbaren UI: ${term}`).toBe(false);
    }
  });

  it("keine Scheingenauigkeit: kein Prozentzeichen im sichtbaren Output", () => {
    const result = assembleSearchResult([makeNote({ id: 1 }), makeNote({ id: 2 })], "x");
    render(<MemoryResultList result={result} roleView={memoryRoleView("technician")} announce />);
    expect(document.body.textContent ?? "").not.toMatch(/%/);
  });
});
