// ============================================================
//  FOREMAN Frontend — lib/prediction/aggregate.ts
//  Zweck: Das Manager-Aggregat (Studie §4E): ein aggregiertes Risikobild über
//         Maschinen — NIE die Einzelempfehlung als Befehl. Aus den jüngsten
//         Vorhersagen je Maschine: verbale Stufe + Entscheidung, nach Risiko
//         sortiert. Keine Scheingenauigkeit, kein Empfehlungstext, keine Aktion.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Funktion.
// ============================================================
import type { FailurePredictionRead } from "@/lib/api/contracts";
import { confidenceLevel } from "./confidence";
import type { ConfidenceLevel } from "./types";

export interface RiskAggregateRow {
  machineId: number;
  level: ConfidenceLevel;
  overThreshold: boolean;
  generatedAt: string;
}

export interface RiskAggregate {
  total: number;
  elevated: number;
  rows: RiskAggregateRow[];
}

/** Sortier-Rang: hohes Risiko zuerst (kritisch oben, wie ISA-18.2 in C). */
const LEVEL_RANK: Record<ConfidenceLevel, number> = { hoch: 0, erhoeht: 1, gering: 2 };

/**
 * Reduziert eine Liste von Vorhersagen (jüngste je Maschine) auf das Risikobild.
 * Mehrere Vorhersagen je Maschine → die jüngste (created_at) gewinnt.
 */
export function buildRiskAggregate(predictions: readonly FailurePredictionRead[]): RiskAggregate {
  const latestByMachine = new Map<number, FailurePredictionRead>();
  for (const p of predictions) {
    const existing = latestByMachine.get(p.machine_id);
    if (!existing || p.created_at > existing.created_at) {
      latestByMachine.set(p.machine_id, p);
    }
  }
  const rows: RiskAggregateRow[] = [...latestByMachine.values()].map((p) => ({
    machineId: p.machine_id,
    level: confidenceLevel(p.probability, p.decision_threshold),
    overThreshold: p.decision === "elevated_risk",
    generatedAt: p.created_at,
  }));
  rows.sort((a, b) => {
    const byLevel = LEVEL_RANK[a.level] - LEVEL_RANK[b.level];
    return byLevel !== 0 ? byLevel : a.machineId - b.machineId;
  });
  return {
    total: rows.length,
    elevated: rows.filter((r) => r.overThreshold).length,
    rows,
  };
}
