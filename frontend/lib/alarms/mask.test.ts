// ============================================================
//  FOREMAN Frontend — lib/alarms/mask.test.ts
//  Zweck: PII-Maskierung (§8) — nie Klartext, nie der volle Token.
// ============================================================
import { describe, expect, it } from "vitest";
import { acknowledgedByLabel, maskAcknowledgedBy } from "./mask";

describe("maskAcknowledgedBy", () => {
  it("HMAC-Token → kurzes pseudonymes Handle (#hex6)", () => {
    expect(maskAcknowledgedBy("v1:a7f3e8c2b9d4f1abcdef")).toBe("#a7f3e8");
  });

  it("zeigt NIE den vollen Token", () => {
    const masked = maskAcknowledgedBy("v1:a7f3e8c2b9d4f1abcdef0123456789");
    expect(masked).not.toBeNull();
    expect((masked as string).length).toBeLessThanOrEqual(7); // '#' + 6 hex
  });

  it("null/leer → null", () => {
    expect(maskAcknowledgedBy(null)).toBeNull();
    expect(maskAcknowledgedBy(undefined)).toBeNull();
    expect(maskAcknowledgedBy("")).toBeNull();
  });

  it("ohne Versions-Präfix robust", () => {
    expect(maskAcknowledgedBy("deadbeef00")).toBe("#deadbe");
  });
});

describe("acknowledgedByLabel", () => {
  it("setzt maskiertes Handle + Zeit zusammen", () => {
    const label = acknowledgedByLabel("v1:a7f3e8c2", "2026-06-17T12:07:00Z");
    expect(label).toContain("#a7f3e8");
    expect(label).toMatch(/quittiert von/);
  });

  it("null-Token → null (nichts anzeigen)", () => {
    expect(acknowledgedByLabel(null, "2026-06-17T12:07:00Z")).toBeNull();
  });
});
