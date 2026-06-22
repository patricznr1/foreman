// ============================================================
//  FOREMAN Frontend — components/event-chains/chains-view.tsx
//  Zweck: Sektions-Einstieg D (Studie §3.1/§4D), Rollen-Split OHNE bedingte Hooks:
//         Manager → verdichtetes Aggregat; Werker/Techniker/Schichtleiter →
//         gespeicherte Ketten lesen, Schichtleiter zusätzlich rekonstruieren (Trigger
//         gegen den Anker-Alarm aus ?anchor), Techniker/Schichtleiter pinnen.
//         Sichtbarkeit ≤ Server-Guard (requireSection("D")).
//  Architektur-Einordnung: Sektions-Einstieg (Schicht 2, client).
// ============================================================
"use client";

import { useEffect, useState } from "react";
import { ResultWithProvenance } from "@/components/ondemand";
import type { CurrentUser } from "@/lib/api/contracts";
import { type ChainRoleView, chainRoleView } from "@/lib/event-chains/roles";
import { useChainDetail } from "@/lib/event-chains/use-saved-chains";
import { ASSEMBLE_FAILURE_TEXT, assembleChainCard } from "@/lib/event-chains/view-model";
import { FiveState } from "@/lib/ui/five-states";
import { ChainTriggerPanel } from "./chain-trigger-panel";
import { ChainsAggregate } from "./chains-aggregate";
import { SavedChainsList } from "./saved-chains-list";
import { TimelineNarrative } from "./timeline-narrative";

export interface ChainsViewProps {
  user: CurrentUser;
  /** Anker-Alarm aus dem Querlink (C/B) — der Anker IST ein Alarm. */
  anchorAlarmId: number | null;
  /** Maschinen-Filter aus dem Querlink (B). */
  machineId: number | null;
  /** Konkret zu öffnende Erklärung (Deep-Link, z. B. aus einem Pin in B). */
  initialExplanationId?: number | null;
}

export function ChainsView({
  user,
  anchorAlarmId,
  machineId,
  initialExplanationId = null,
}: ChainsViewProps) {
  const roleView = chainRoleView(user.role);
  // Manager sieht NUR das Aggregat — eigener Zweig, keine bedingten Hooks.
  if (roleView.aggregateOnly) {
    return <ChainsAggregate />;
  }
  return (
    <ChainsSingle
      roleView={roleView}
      anchorAlarmId={anchorAlarmId}
      machineId={machineId}
      initialExplanationId={initialExplanationId}
    />
  );
}

function ChainsSingle({
  roleView,
  anchorAlarmId,
  machineId,
  initialExplanationId,
}: {
  roleView: ChainRoleView;
  anchorAlarmId: number | null;
  machineId: number | null;
  initialExplanationId: number | null;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(initialExplanationId);
  // Deep-Link-Auswahl nachführen, wenn sich der Anker-Parameter später ändert
  // (z. B. neue ?explanation=-Navigation auf derselben Route).
  useEffect(() => {
    setSelectedId(initialExplanationId);
  }, [initialExplanationId]);
  const detail = useChainDetail(selectedId);

  return (
    <section className="flex flex-col gap-5" aria-label="Ereignisketten">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-fg-primary">Ereignisketten</h1>
        <p className="text-body text-fg-secondary">
          Rekonstruierte Erzählung entlang der Zeit um einen Anker-Alarm — belegte
          Ereignisse und rekonstruierte Erzählung hart getrennt.
        </p>
      </div>

      {/* Trigger-Flow: nur Schichtleiter, nur mit Anker-Alarm aus dem Querlink. */}
      {roleView.canTrigger && anchorAlarmId !== null ? (
        <ChainTriggerPanel
          anchorAlarmId={anchorAlarmId}
          canPin={roleView.canPin}
          onOpenSibling={setSelectedId}
        />
      ) : anchorAlarmId !== null ? (
        <p role="status" className="rounded-lg border border-line-subtle bg-surface-raised p-3 text-caption text-fg-muted">
          Rekonstruktion ist dem Schichtleiter vorbehalten — gespeicherte Ketten lassen sich hier lesen.
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,20rem)_1fr]">
        <div className="flex flex-col gap-2">
          <h2 className="text-h2 text-fg-primary">Gespeicherte Ketten</h2>
          <SavedChainsList machineId={machineId} selectedId={selectedId} onOpen={setSelectedId} />
        </div>
        <div className="min-w-0">
          <FiveState
            state={detail}
            label="Kette"
            empty={
              <div role="status" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted">
                Wähle links eine gespeicherte Kette, um sie zu öffnen.
              </div>
            }
          >
            {(data, freshness) => {
              const result = assembleChainCard(data);
              if (!result.ok) {
                return (
                  <div role="alert" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-note-caveat">
                    {ASSEMBLE_FAILURE_TEXT[result.reason]}
                  </div>
                );
              }
              const { card } = result;
              const basis = card.recallUsed
                ? "Datenbasis: belegte Ereignisse + ähnliche Vergangenheitsfälle"
                : "Datenbasis: belegte Ereignisse";
              return (
                <ResultWithProvenance
                  freshness={freshness}
                  stampedAt={card.stampedAt}
                  aiGenerated
                  caveat={card.isHypothesis}
                  basis={basis}
                >
                  <TimelineNarrative card={card} canPin={roleView.canPin} onOpenSibling={setSelectedId} />
                </ResultWithProvenance>
              );
            }}
          </FiveState>
        </div>
      </div>
    </section>
  );
}
