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
import type { CurrentUser } from "@/lib/api/contracts";
import { type ChainRoleView, chainRoleView } from "@/lib/event-chains/roles";
import { ChainTriggerPanel } from "./chain-trigger-panel";
import { ChainsAggregate } from "./chains-aggregate";
import { SavedChainsBrowser } from "./saved-chains-browser";

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

      <SavedChainsBrowser
        machineId={machineId}
        selectedId={selectedId}
        onSelect={setSelectedId}
        canPin={roleView.canPin}
      />
    </section>
  );
}
