// ============================================================
//  FOREMAN Frontend — lib/memory/url.test.ts
//  Zweck: BFF-Pfad der F-SEM-Suche — Form, Encoding, optionaler Maschinen-Filter.
// ============================================================
import { describe, expect, it } from "vitest";
import { DEFAULT_SEARCH_K, searchNotesEndpoint } from "./url";

describe("searchNotesEndpoint", () => {
  it("baut den relativen BFF-Pfad mit q und Default-k", () => {
    const url = searchNotesEndpoint("Lager heiß");
    expect(url).toContain("/api/v1/worker_notes/search?");
    expect(url).toContain(`k=${DEFAULT_SEARCH_K}`);
    // Freitext wird URL-kodiert (Leerzeichen, Umlaut).
    expect(url).toContain("q=Lager+hei%C3%9F");
  });

  it("lässt machine_id weg, wenn null", () => {
    expect(searchNotesEndpoint("test", null)).not.toContain("machine_id");
  });

  it("hängt machine_id an, wenn gesetzt", () => {
    expect(searchNotesEndpoint("test", 42)).toContain("machine_id=42");
  });

  it("respektiert ein explizites k", () => {
    expect(searchNotesEndpoint("test", null, 5)).toContain("k=5");
  });
});
