// ============================================================
//  FOREMAN Frontend — lib/event-chains/confidence.ts
//  Zweck: Verbale Konfidenz-Stufe der Erzählung (Studie §4D): low/medium/high →
//         gering/mittel/hoch — NIE als Prozent. Kein Severity-Bezug (ISA-101-Ruhe).
//  Architektur-Einordnung: reine Abbildung (Schicht 2).
// ============================================================
import type { Confidence } from "@/lib/api/contracts";
import type { ConfidenceLevel } from "./types";

const CONFIDENCE_LEVEL: Record<Confidence, ConfidenceLevel> = {
  low: "gering",
  medium: "mittel",
  high: "hoch",
};

export function confidenceLevel(confidence: Confidence): ConfidenceLevel {
  return CONFIDENCE_LEVEL[confidence] ?? "gering";
}

/** Klartext-Label der Konfidenz-Stufe (farbunabhängig, verbal). */
export const CONFIDENCE_LABEL: Record<ConfidenceLevel, string> = {
  gering: "geringe Konfidenz",
  mittel: "mittlere Konfidenz",
  hoch: "hohe Konfidenz",
};

export function confidenceLabel(confidence: Confidence): string {
  return CONFIDENCE_LABEL[confidenceLevel(confidence)];
}
