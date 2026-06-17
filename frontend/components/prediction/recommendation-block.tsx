// ============================================================
//  FOREMAN Frontend — components/prediction/recommendation-block.tsx
//  Zweck: Block 3 (Empfehlung, Studie §4E). Klar abgesetzter Handlungsblock, IMMER
//         als Vorschlag formuliert, NIE als Befehl, NIE mit einer Schalt-Aktion
//         verknüpft (HITL). Wer entscheiden darf, quittiert/verwirft mit Begründung
//         (DecisionAction); eine getroffene Entscheidung wird auditierbar angezeigt.
//  Architektur-Einordnung: Block-Komponente (Schicht 2). Rein präsentational.
// ============================================================
"use client";

import type { RiskDecision } from "@/lib/api/contracts";
import type { DecisionDisposition, DecisionRecord } from "@/lib/prediction/decision";
import type { RecommendationModel } from "@/lib/prediction/types";
import { DecisionAction } from "./decision-action";

export interface RecommendationBlockProps {
  recommendation: RecommendationModel;
  decision: RiskDecision;
  canDecide: boolean;
  onDecide?: (disposition: DecisionDisposition, reason: string | null) => void;
  pending?: boolean;
  decided?: DecisionRecord | null;
}

const DISPOSITION_TEXT: Record<DecisionDisposition, string> = {
  acknowledged: "Quittiert",
  dismissed: "Verworfen",
};

function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

function DecisionSummary({ decided }: { decided: DecisionRecord }) {
  const time = formatTime(decided.atIso);
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-line-subtle bg-surface-raised p-3">
      <p className="text-body text-fg-primary">
        {DISPOSITION_TEXT[decided.disposition]}
        {time ? ` um ${time}` : ""}
      </p>
      {decided.reason ? (
        <p className="text-caption text-fg-muted">Begründung: {decided.reason}</p>
      ) : null}
    </div>
  );
}

export function RecommendationBlock({
  recommendation,
  decision,
  canDecide,
  onDecide,
  pending = false,
  decided = null,
}: RecommendationBlockProps) {
  return (
    <section
      data-block="recommendation"
      aria-label="Empfehlung"
      className="flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised p-4"
    >
      <div className="flex flex-col gap-1">
        <h3 className="text-caption font-semibold uppercase tracking-wide text-fg-muted">
          Empfehlung — Vorschlag an Sie
        </h3>
        <p className="text-body-l text-fg-primary">{recommendation.text}</p>
        {recommendation.sourceCount > 0 ? (
          <p className="text-caption text-fg-muted">
            belegt über {recommendation.sourceCount}{" "}
            {recommendation.sourceCount === 1 ? "Quelle" : "Quellen"}
          </p>
        ) : null}
      </div>
      {decided !== null ? (
        <DecisionSummary decided={decided} />
      ) : canDecide && onDecide ? (
        <DecisionAction decision={decision} onDecide={onDecide} pending={pending} />
      ) : (
        <p className="text-caption text-fg-muted">
          Quittieren/Verwerfen ist dieser Rolle nicht zugewiesen.
        </p>
      )}
    </section>
  );
}
