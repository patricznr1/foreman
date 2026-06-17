// ============================================================
//  FOREMAN Frontend — lib/capture/url.test.ts
//  Zweck: Sichert die REALE Erfassungs-Route (relativer BFF-Pfad).
// ============================================================
import { describe, expect, it } from "vitest";
import { createNoteEndpoint } from "./url";

describe("createNoteEndpoint", () => {
  it("zeigt auf den realen worker_notes-POST über den BFF-Proxy", () => {
    expect(createNoteEndpoint()).toBe("/api/v1/worker_notes");
  });

  it("ist ein relativer Pfad (BFF injiziert das JWT, kein Backend-Origin)", () => {
    expect(createNoteEndpoint().startsWith("/api/v1/")).toBe(true);
  });
});
