// ============================================================
//  FOREMAN Frontend — lib/ui/pii.test.ts
//  Zweck: Sichert die PII-Maskierung — HMAC-Pseudonym-Token → kurzes #hex6-Handle.
// ============================================================
import { describe, expect, it } from "vitest";

import { maskPseudonym } from "./pii";

describe("maskPseudonym", () => {
  it("kürzt ein versioniertes HMAC-Token auf #hex6 (Versions-Präfix entfällt)", () => {
    expect(maskPseudonym("v1:a7f3e8c9d0b1f2a3")).toBe("#a7f3e8");
  });

  it("ohne Versions-Präfix: erste sechs Hexzeichen", () => {
    expect(maskPseudonym("abcdef0123456789")).toBe("#abcdef");
  });

  it("null/undefined/leer → null (nie Klartext, nie #anonym aus dem Nichts)", () => {
    expect(maskPseudonym(null)).toBeNull();
    expect(maskPseudonym(undefined)).toBeNull();
    expect(maskPseudonym("")).toBeNull();
  });
});
