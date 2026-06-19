// ============================================================
//  FOREMAN Frontend — components/event-chains/chain-trigger-panel.tsx
//  Zweck: Der On-Demand-Trigger der Rekonstruktion (Studie §3.2/§4D): „Kette
//         rekonstruieren" gegen einen Anker-ALARM → benannter Verarbeitungszustand
//         („verknüpfe Ereignisse über die Klasse …") → Ergebnis (TimelineNarrative)
//         mit Herkunftsstempel. Erbt das GETEILTE Muster aus E. Degradation:
//         offline → Trigger deaktiviert mit Grund; frühere Ergebnisse bleiben.
//         Die Erzählung ist KI-erzeugt → ProvenanceStamp trägt „KI-erzeugt".
//  Architektur-Einordnung: Sektions-Orchestrierung (Schicht 2).
// ============================================================
"use client";

import type { ReactNode } from "react";
import { NamedProcessingState, ResultWithProvenance, TriggerButton } from "@/components/ondemand";
import type { ReasonerExplanationDetailRead } from "@/lib/api/contracts";
import { previousResult } from "@/lib/ondemand/machine";
import { useOnline } from "@/lib/ondemand/use-online";
import { useChainReconstruction } from "@/lib/event-chains/use-chains";
import { ASSEMBLE_FAILURE_TEXT, assembleChainCard } from "@/lib/event-chains/view-model";
import { TimelineNarrative } from "./timeline-narrative";

const PROCESSING_MESSAGE = "Verknüpfe Ereignisse über die Klasse …";

function Notice({ tone, role, children }: {
  tone: "muted" | "caveat";
  role: "status" | "alert";
  children: ReactNode;
}) {
  const color = tone === "caveat" ? "text-note-caveat" : "text-fg-muted";
  return (
    <div
      role={role}
      className={`flex min-h-24 items-center rounded-lg border border-line-subtle bg-surface-raised p-4 text-body ${color}`}
    >
      {children}
    </div>
  );
}

export interface ChainTriggerPanelProps {
  anchorAlarmId: number;
  canPin: boolean;
  onOpenSibling: (explanationId: number) => void;
}

export function ChainTriggerPanel({ anchorAlarmId, canPin, onOpenSibling }: ChainTriggerPanelProps) {
  const online = useOnline();
  const { phase, trigger, busy } = useChainReconstruction(anchorAlarmId);

  function renderResult(detail: ReasonerExplanationDetailRead, stampedAt: string) {
    const result = assembleChainCard(detail);
    if (!result.ok) {
      return (
        <Notice tone="caveat" role="alert">
          {ASSEMBLE_FAILURE_TEXT[result.reason]}
        </Notice>
      );
    }
    const { card } = result;
    const basis = card.recallUsed
      ? "Datenbasis: belegte Ereignisse + ähnliche Vergangenheitsfälle"
      : "Datenbasis: belegte Ereignisse";
    return (
      <ResultWithProvenance freshness="cached" stampedAt={stampedAt} aiGenerated caveat={card.isHypothesis} basis={basis}>
        <TimelineNarrative card={card} canPin={canPin} onOpenSibling={onOpenSibling} />
      </ResultWithProvenance>
    );
  }

  const previous = previousResult(phase);
  let body: ReactNode;
  if (phase.kind === "processing") {
    body = (
      <div className="flex flex-col gap-4">
        <NamedProcessingState message={PROCESSING_MESSAGE} />
        {previous ? renderResult(previous.data, previous.stampedAt) : null}
      </div>
    );
  } else if (phase.kind === "result") {
    body = renderResult(phase.result.data, phase.result.stampedAt);
  } else if (phase.kind === "error") {
    body = (
      <div className="flex flex-col gap-4">
        <Notice tone="caveat" role="alert">{phase.message}</Notice>
        {previous ? renderResult(previous.data, previous.stampedAt) : null}
      </div>
    );
  } else {
    body = previous ? (
      renderResult(previous.data, previous.stampedAt)
    ) : (
      <Notice tone="muted" role="status">
        Noch keine Kette — gegen den Anker-Alarm rekonstruieren.
      </Notice>
    );
  }

  return (
    <section className="flex flex-col gap-4" aria-label={`Kette rekonstruieren — Alarm #${anchorAlarmId}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-h2 text-fg-primary">Anker-Alarm #{anchorAlarmId}</h2>
        <TriggerButton
          label="Kette rekonstruieren"
          busyLabel="Rekonstruiere …"
          busy={busy}
          disabledReason={online ? null : "Offline — Rekonstruktion nicht möglich (Stand siehe Stempel)"}
          onTrigger={() => trigger()}
        />
      </div>
      {body}
    </section>
  );
}
