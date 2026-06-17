// ============================================================
//  FOREMAN Frontend — lib/prediction/aggregate.test.ts
//  Zweck: Manager-Aggregat — jüngste je Maschine, nach Risiko sortiert, kein
//         Empfehlungstext (nie die Einzelempfehlung als Befehl).
// ============================================================
import { describe, expect, it } from "vitest";
import { buildRiskAggregate } from "./aggregate";
import { makePrediction } from "./testing/fixtures";

describe("buildRiskAggregate", () => {
  it("nimmt je Maschine die JÜNGSTE Vorhersage", () => {
    const agg = buildRiskAggregate([
      makePrediction({ machine_id: 7, created_at: "2026-06-17T07:00:00Z", probability: 0.2, decision: "normal" }),
      makePrediction({ machine_id: 7, created_at: "2026-06-17T08:00:00Z", probability: 0.9, decision: "elevated_risk" }),
    ]);
    expect(agg.total).toBe(1);
    expect(agg.elevated).toBe(1);
    expect(agg.rows[0]!.level).toBe("hoch");
  });

  it("vergleicht created_at über Epoch, nicht als String (abweichende Zeitzonen)", () => {
    // "09:00+02:00" = 07:00 UTC liegt VOR "08:00Z" = 08:00 UTC — ein String-
    // Vergleich („09" > „08") würde fälschlich die frühere Vorhersage wählen.
    const agg = buildRiskAggregate([
      makePrediction({ machine_id: 5, created_at: "2026-06-17T09:00:00+02:00", probability: 0.1, decision_threshold: 0.5, decision: "normal" }),
      makePrediction({ machine_id: 5, created_at: "2026-06-17T08:00:00Z", probability: 0.95, decision_threshold: 0.5, decision: "elevated_risk" }),
    ]);
    expect(agg.total).toBe(1);
    expect(agg.rows[0]!.overThreshold).toBe(true); // die spätere (08:00Z) gewinnt
    expect(agg.rows[0]!.level).toBe("hoch");
  });

  it("sortiert hohes Risiko nach oben (kritisch oben, wie ISA-18.2 in C)", () => {
    const agg = buildRiskAggregate([
      makePrediction({ id: 1, machine_id: 1, probability: 0.2, decision_threshold: 0.5, decision: "normal" }),
      makePrediction({ id: 2, machine_id: 2, probability: 0.95, decision_threshold: 0.5, decision: "elevated_risk" }),
      makePrediction({ id: 3, machine_id: 3, probability: 0.6, decision_threshold: 0.5, decision: "elevated_risk" }),
    ]);
    expect(agg.rows.map((r) => r.machineId)).toEqual([2, 3, 1]);
    expect(agg.total).toBe(3);
    expect(agg.elevated).toBe(2);
  });

  it("liefert nur aggregierte Felder — keinen Empfehlungstext", () => {
    const agg = buildRiskAggregate([makePrediction()]);
    expect(agg.rows[0]).not.toHaveProperty("recommendation");
    expect(agg.rows[0]).not.toHaveProperty("text");
  });
});
