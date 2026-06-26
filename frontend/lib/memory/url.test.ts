// ============================================================
//  FOREMAN Frontend — lib/memory/url.test.ts
//  Zweck: BFF-Pfade — Notiz-Suche (Kontextvorschlag J) + Archiv-Suche (1c, mit
//         machine_id + sources[]). Form, Encoding, optionale Parameter.
// ============================================================
import { describe, expect, it } from "vitest";
import { DEFAULT_SEARCH_K, searchArchiveEndpoint, searchNotesEndpoint } from "./url";

describe("searchNotesEndpoint", () => {
  it("baut den relativen BFF-Pfad mit q und Default-k", () => {
    const url = searchNotesEndpoint("Lager heiß");
    expect(url).toContain("/api/v1/worker_notes/search?");
    expect(url).toContain(`k=${DEFAULT_SEARCH_K}`);
    expect(url).toContain("q=Lager+hei%C3%9F");
  });

  it("lässt machine_id weg, wenn null; hängt es an, wenn gesetzt", () => {
    expect(searchNotesEndpoint("test", null)).not.toContain("machine_id");
    expect(searchNotesEndpoint("test", 42)).toContain("machine_id=42");
  });
});

describe("searchArchiveEndpoint", () => {
  it("baut den relativen BFF-Pfad mit q und Default-k", () => {
    const url = searchArchiveEndpoint("Fett");
    expect(url).toContain("/api/v1/archive/search?");
    expect(url).toContain(`k=${DEFAULT_SEARCH_K}`);
    expect(url).toContain("q=Fett");
  });

  it("lässt machine_id und sources weg, wenn null/leer", () => {
    const url = searchArchiveEndpoint("x", null, null);
    expect(url).not.toContain("machine_id");
    expect(url).not.toContain("sources");
  });

  it("hängt machine_id an, wenn gesetzt", () => {
    expect(searchArchiveEndpoint("x", 42)).toContain("machine_id=42");
  });

  it("serialisiert die aktiven Quellen als CSV", () => {
    // URLSearchParams kodiert das Komma als %2C.
    expect(searchArchiveEndpoint("x", null, ["note", "alarm"])).toContain("sources=note%2Calarm");
  });

  it("lässt sources weg, wenn leer (Backend-Default = alle Quellen)", () => {
    expect(searchArchiveEndpoint("x", null, [])).not.toContain("sources");
  });
});
