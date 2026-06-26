// ============================================================
//  FOREMAN Frontend — components/memory/hidden-term.test.tsx
//  Zweck: STRENGSTES Gate der Serie (Studie §0/§1.3/§4H, GROUND_TRUTH §17 III):
//         im sichtbaren UI des ARCHIVS erscheint KEIN interner Verfahrens-/
//         Bibliotheks-/Substrat-Name — die Fähigkeit spricht reine Hallensprache
//         ("Stichwort", "Treffer", "Archiv"). Zusätzlich: keine Scheingenauigkeit
//         (kein Prozentzeichen). Geprüft über alle drei Quellen.
// ============================================================
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { memoryRoleView } from "@/lib/memory/roles";
import { makeArchiveHit } from "@/lib/memory/testing/fixtures";
import { assembleArchiveResult } from "@/lib/memory/view-model";
import { MemoryResultList } from "./memory-result-list";
import { MemorySearchBar } from "./memory-search-bar";

// Interne Begriffe aus dem Innenleben des Archivs (F-SEM) — nie sichtbar.
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
  it("kein interner Verfahrensbegriff erscheint im sichtbaren Output (alle drei Quellen)", () => {
    const result = assembleArchiveResult(
      [
        makeArchiveHit({ source_type: "note", id: 1, detail: { shift: "Früh" } }),
        makeArchiveHit({
          source_type: "maintenance",
          id: 2,
          excerpt: "Schmierung erneuert.",
          detail: { type: "lubrication" },
        }),
        makeArchiveHit({
          source_type: "alarm",
          id: 3,
          excerpt: "Beleuchtung defekt.",
          detail: { severity: "warning", category: "process", code: "ILL-7" },
        }),
      ],
      "Lager läuft heiß",
      ["note", "maintenance", "alarm"],
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
    const result = assembleArchiveResult(
      [makeArchiveHit({ id: 1 }), makeArchiveHit({ id: 2 })],
      "x",
      ["note"],
    );
    render(<MemoryResultList result={result} roleView={memoryRoleView("technician")} announce />);
    expect(document.body.textContent ?? "").not.toMatch(/%/);
  });
});
