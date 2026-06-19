// ============================================================
//  FOREMAN Frontend — lib/event-chains/view-model.ts
//  Zweck: Setzt aus der Detail-Erklärung (F-REC) das ChainCardModel zusammen — die
//         HARTE Trennung von BELEGT (Kettenknoten) und ERZÄHLT (rekonstruierte
//         Erzählung, Hypothese, Konfidenz, geflaggte Inhalte), Kern von §4D.
//         Eingefrorene Altdatensätze ohne Snapshot (`chain=null`) sind graceful:
//         die Erzählung bleibt sichtbar, die Zeitachse ist als nicht verfügbar
//         markiert (kein erfundener Verlauf). Reine Funktion.
//  Architektur-Einordnung: View-State-Komposition (Schicht 2).
// ============================================================
import type { ReasonerExplanationDetailRead, ReasonerExplanationRead } from "@/lib/api/contracts";
import { confidenceLevel } from "./confidence";
import { parseNarrative } from "./narrative";
import { toSiblingModels } from "./siblings";
import { buildNodes } from "./timeline";
import type { ChainCardModel, ChainSummaryModel } from "./types";

export type AssembleFailure = "empty-narrative";

export type AssembleResult =
  | { ok: true; card: ChainCardModel }
  | { ok: false; reason: AssembleFailure };

/** Hallensprache zu einem Nicht-Karte-Grund (defensiver Fehler-Zustand). */
export const ASSEMBLE_FAILURE_TEXT: Record<AssembleFailure, string> = {
  "empty-narrative": "Erklärung ohne Erzähltext — nicht anzeigbar (Datenfehler)",
};

/**
 * Baut die Ketten-Karte. BELEGT = die Knoten aus dem eingefrorenen Snapshot;
 * ERZÄHLT = die in Segmente zerlegte Erzählung. Beide werden gemeinsam getragen,
 * hart getrennt dargestellt. Ohne Erzähltext gibt es keine Karte (defensiv).
 */
export function assembleChainCard(detail: ReasonerExplanationDetailRead): AssembleResult {
  if (detail.narrative.trim().length === 0) {
    return { ok: false, reason: "empty-narrative" };
  }
  const chainAvailable = detail.chain !== null;
  const nodes = detail.chain !== null ? buildNodes(detail.chain) : [];
  const window =
    detail.chain !== null
      ? { startIso: detail.chain.window.start, endIso: detail.chain.window.end }
      : null;
  const card: ChainCardModel = {
    explanationId: detail.id,
    anchorAlarmId: detail.anchor_alarm_id,
    machineId: detail.machine_id,
    chainAvailable,
    nodes,
    window,
    narrativeSegments: parseNarrative(detail.narrative),
    isHypothesis: detail.is_hypothesis,
    confidence: confidenceLevel(detail.confidence),
    flagged: [...detail.flagged_unsupported],
    recallUsed: detail.recall_used,
    grounded: detail.grounded,
    stampedAt: detail.created_at,
    siblings: toSiblingModels(detail.siblings),
  };
  return { ok: true, card };
}

/**
 * Verdichtet eine gespeicherte Erklärung zu einem Ein-Satz-Modell (Manager-Sicht,
 * Studie §4D: „ein Satz + Kennzahl", nie die volle Erzählung).
 */
export function toSummary(read: ReasonerExplanationRead): ChainSummaryModel {
  const level = confidenceLevel(read.confidence);
  const machinePart = read.machine_id !== null ? `Maschine ${read.machine_id}` : "unbekannte Maschine";
  const hypothesisPart = read.is_hypothesis ? ", als Hypothese gekennzeichnet" : "";
  return {
    explanationId: read.id,
    anchorAlarmId: read.anchor_alarm_id,
    machineId: read.machine_id,
    confidence: level,
    isHypothesis: read.is_hypothesis,
    createdAtIso: read.created_at,
    sentence: `Rekonstruierte Kette um Alarm ${read.anchor_alarm_id} an ${machinePart} (${level}e Konfidenz${hypothesisPart}).`,
  };
}
