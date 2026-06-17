// ============================================================
//  FOREMAN Frontend — lib/prediction/decision.test.ts
//  Zweck: HITL — quittieren/verwerfen auditierbar, Begründungs-Pflicht, und der
//         NEGATIVTEST: keine Entscheidung erreicht je einen Anlagen-/Aktor-Pfad.
// ============================================================
import { describe, expect, it } from "vitest";
import {
  buildDecisionRecord,
  isPredictionAuditActionPath,
  predictionDecisionEndpoint,
  requiresDecisionReason,
} from "./decision";

const CARD = { predictionId: 101, recommendationId: 555, machineId: 7, decision: "elevated_risk" } as const;

describe("requiresDecisionReason", () => {
  it("verlangt eine Begründung beim Verwerfen — immer", () => {
    expect(requiresDecisionReason("dismissed", "normal")).toBe(true);
  });
  it("verlangt eine Begründung bei erhöhtem Risiko — jede Disposition", () => {
    expect(requiresDecisionReason("acknowledged", "elevated_risk")).toBe(true);
  });
  it("lässt Quittieren bei geringem Risiko ohne Begründung zu", () => {
    expect(requiresDecisionReason("acknowledged", "normal")).toBe(false);
  });
});

describe("buildDecisionRecord — auditierbar (wer/wann/warum)", () => {
  it("baut einen Datensatz mit Bezug, Disposition und getrimmter Begründung", () => {
    const rec = buildDecisionRecord(CARD, "acknowledged", "  Schmierung vorgezogen  ", "2026-06-17T09:00:00Z");
    expect(rec).toEqual({
      predictionId: 101,
      recommendationId: 555,
      machineId: 7,
      disposition: "acknowledged",
      reason: "Schmierung vorgezogen",
      atIso: "2026-06-17T09:00:00Z",
    });
  });

  it("wirft, wenn eine Pflicht-Begründung fehlt (zweite Linie zum UI-Guard)", () => {
    expect(() => buildDecisionRecord(CARD, "dismissed", null, "2026-06-17T09:00:00Z")).toThrow();
    expect(() => buildDecisionRecord(CARD, "dismissed", "   ", "2026-06-17T09:00:00Z")).toThrow();
  });
});

describe("NEGATIVTEST — keine Aktorik, kein Schreibpfad", () => {
  it("hat HEUTE keine Backend-Route für die Entscheidung (bleibt client-seitig)", () => {
    expect(predictionDecisionEndpoint()).toBeNull();
  });

  it("erkennt KEINEN Anlagen-/Aktor-Pfad als zulässige Entscheidungs-Route", () => {
    for (const path of [
      "/api/v1/machines/7/actuate",
      "/api/v1/machines/7/control",
      "/api/v1/machines/7/setpoint",
      "/api/v1/machines/7/switch",
      "/api/v1/reasoners/failure/predict",
      "/api/v1/machines/7/command",
    ]) {
      expect(isPredictionAuditActionPath(path)).toBe(false);
    }
  });

  it("lässt ausschließlich den (künftigen) Audit-Append-Pfad zu — nie etwas Schaltbares", () => {
    expect(isPredictionAuditActionPath("/api/v1/audit/decisions")).toBe(true);
  });
});
