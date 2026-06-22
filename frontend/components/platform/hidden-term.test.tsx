// ============================================================
//  FOREMAN Frontend — components/platform/hidden-term.test.tsx
//  Zweck: Hidden-Term-Gate der Sektion I (Paraphrase-Disziplin §8/§22.2): KEIN
//         internes Vokabel des Gedächtnis-Substrats (NEXUS-Interna, Embedding-/
//         Vektor-/Index-/Reasoner-Begriffe) im sichtbaren UI. Das Substrat heißt
//         nach außen NUR „Gedächtnis-Substrat", die F7-Grenze „MCP-Schnittstelle"
//         (beides sanktioniert). Gescannt wird das von UNS gerenderte Chrome mit
//         NEUTRALEN Fixtures (Backend-Daten sind kein Wording).
// ============================================================
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CurrentUser } from "@/lib/api/contracts";
import { makeAuditEntry, makeTopologyView } from "@/lib/platform/testing/fixtures";
import { PlatformView } from "./platform-view";

const MANAGER: CurrentUser = {
  id: 1,
  email: "m@example.com",
  role: "manager",
  assigned_line_ids: [],
  assigned_machine_ids: [],
};

// Internes Innenleben des Substrats + Verfahrensbegriffe — dürfen NIE im UI stehen.
// (NICHT verboten: „Substrat"/„Gedächtnis-Substrat" und „MCP" — die sind die
//  sanktionierten Außen-Bezeichnungen.)
const FORBIDDEN = [
  "nexus",
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
  "adwin",
  "dowhy",
  "sparql",
  "qwen",
  "vllm",
  "reasoner",
  "gateway",
  "prompt",
];

function jsonResponse(payload: unknown): Response {
  return { ok: true, status: 200, json: async () => payload } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Hidden-Term-Scan (Sektion I)", () => {
  it("kein internes Vokabel im sichtbaren Plattform-/Audit-UI", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/topology")) {
          return Promise.resolve(jsonResponse(makeTopologyView()));
        }
        // Neutrale Audit-Daten (kein Verfahrens-Wording in der detail-JSONB).
        return Promise.resolve(
          jsonResponse([
            makeAuditEntry({
              actor: `v1:${"a".repeat(64)}`,
              detail: { decision: "acknowledged" },
            }),
          ]),
        );
      }),
    );

    render(<PlatformView user={MANAGER} />);
    await screen.findByTestId("topology-graph");
    // Audit-Panel ist (verdeckt) gemountet → seine Zeilen sind im DOM; warten bis geladen.
    await screen.findByText("#aaaaaa");

    const text = (document.body.textContent ?? "").toLowerCase();
    for (const term of FORBIDDEN) {
      expect(text.includes(term), `verbotener Begriff im sichtbaren UI: ${term}`).toBe(false);
    }
    // Die sanktionierte Außen-Bezeichnung ist dagegen ausdrücklich vorhanden.
    expect(text).toContain("gedächtnis-substrat");
  });
});
