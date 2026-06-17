// ============================================================
//  FOREMAN Frontend — components/prediction/confidence-caveat-card.tsx
//  Zweck: Das Herzstück (Studie §4E/§5.5) — die ConfidenceCaveatCard. EIN
//         gemeinsamer Rahmen für die VIER Blöcke in FESTER Reihenfolge:
//         (1) Konfidenz → (2) Einflussfaktoren → (3) Empfehlung → (4) Vorbehalt.
//         Der Vorbehalt sitzt im SELBEN Rahmen wie die Konfidenz, ist NIE
//         wegklappbar und nie unter „mehr": man kann die Zahl nicht sehen, ohne
//         den Vorbehalt zu sehen. Die Karte existiert strukturell nur mit allen
//         vier Blöcken — es gibt keinen Schalter, der Block 4 ausblendet.
//  Architektur-Einordnung: Komposition (Schicht 2). Rein präsentational.
// ============================================================
"use client";

import type { DecisionDisposition, DecisionRecord } from "@/lib/prediction/decision";
import type { PredictionRoleView } from "@/lib/prediction/roles";
import type { PredictionCardModel } from "@/lib/prediction/types";
import { CaveatBlock } from "./caveat-block";
import { ConfidenceBand } from "./confidence-band";
import { PredictionCrossLinks } from "./cross-links";
import { InfluenceFactorList } from "./influence-factor-list";
import { RecommendationBlock } from "./recommendation-block";

export interface ConfidenceCaveatCardProps {
  card: PredictionCardModel;
  roleView: PredictionRoleView;
  onDecide?: (disposition: DecisionDisposition, reason: string | null) => void;
  pending?: boolean;
  decided?: DecisionRecord | null;
}

export function ConfidenceCaveatCard({
  card,
  roleView,
  onDecide,
  pending = false,
  decided = null,
}: ConfidenceCaveatCardProps) {
  return (
    <article
      aria-label="Ausfallvorhersage und Empfehlung"
      className="flex w-full max-w-2xl flex-col gap-5 rounded-lg border border-line-strong bg-surface-canvas p-5"
    >
      {/* FESTE Reihenfolge: Zahl → Warum → Tu-das → Aber-bedenke. */}
      <ConfidenceBand confidence={card.confidence} horizonH={card.horizonH} />
      <InfluenceFactorList factors={card.factors} detail={roleView.factorDetail} />
      <RecommendationBlock
        recommendation={card.recommendation}
        decision={card.decision}
        canDecide={roleView.canDecide}
        onDecide={onDecide}
        pending={pending}
        decided={decided}
      />
      {/* Block 4 — untrennbar im selben Rahmen, nie wegklappbar. */}
      <CaveatBlock caveat={card.caveat} />
      <PredictionCrossLinks machineId={card.machineId} />
    </article>
  );
}
