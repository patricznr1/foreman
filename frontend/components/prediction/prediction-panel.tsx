// ============================================================
//  FOREMAN Frontend — components/prediction/prediction-panel.tsx
//  Zweck: Die On-Demand-Sicht je Maschine (Werker/Techniker/Schichtleiter). Bindet
//         das GETEILTE On-Demand-Muster (Trigger → benannter Zustand → Ergebnis mit
//         Herkunft) an die ConfidenceCaveatCard. Fünf Pflichtzustände + Degradation:
//         offline → Trigger deaktiviert mit Grund; frühere Ergebnisse bleiben mit
//         Stand sichtbar (kein Leerlaufen). HITL-Entscheidung lokal + auditierbar.
//  Architektur-Einordnung: Sektions-Orchestrierung (Schicht 2).
// ============================================================
"use client";

import { useState } from "react";
import {
  NamedProcessingState,
  ResultWithProvenance,
  TriggerButton,
} from "@/components/ondemand";
import { previousResult } from "@/lib/ondemand/machine";
import { useOnline } from "@/lib/ondemand/use-online";
import { dataRegimeLabel } from "@/lib/prediction/caveat";
import {
  buildDecisionRecord,
  type DecisionDisposition,
  type DecisionRecord,
} from "@/lib/prediction/decision";
import type { PredictionRoleView } from "@/lib/prediction/roles";
import type { PredictionPair } from "@/lib/prediction/types";
import { MAX_VERSUCHE, usePrediction } from "@/lib/prediction/use-prediction";
import { ASSEMBLE_FAILURE_TEXT, assemblePredictionCard } from "@/lib/prediction/view-model";
import { ConfidenceCaveatCard } from "./confidence-caveat-card";

const PROCESSING_MESSAGE = "Werte die aktuelle Lage gegen vergangene Verläufe aus …";

/**
 * Wartetext ab dem zweiten Versuch.
 *
 * Er sagt AUSDRÜCKLICH, warum es länger dauert. Eine Wartemeldung, die beim
 * dritten Versuch genauso aussieht wie beim ersten, lässt den Wartenden vor einer
 * Anzeige stehen, die dreimal so lange braucht wie sonst — und nichts erklärt.
 * Und sie sagt es EHRLICH: Die vorige Fassung wurde verworfen, weil sie nicht
 * durchgehend belegbar war, nicht weil etwas kaputt ist.
 */
export function processingMessage(versuch: number): string {
  return versuch <= 1
    ? PROCESSING_MESSAGE
    : `Die vorige Fassung war nicht durchgehend belegbar — Versuch ${versuch} von ${MAX_VERSUCHE} läuft …`;
}

/** Ruhiger Hinweis (Fehler/leer) — Hallensprache, kein Alarm-Rot. */
function Notice({ tone, role, children }: {
  tone: "muted" | "caveat";
  role: "status" | "alert";
  children: React.ReactNode;
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

export function PredictionPanel({
  machineId,
  roleView,
  label,
  heading,
}: {
  machineId: number;
  roleView: PredictionRoleView;
  label: string;
  /**
   * Sichtbare Überschrift. Vorgabe: `label` (die Maschine) — in Sektion E ist das
   * richtig, dort IST die Maschine der Gegenstand. Eingebettet in die
   * Maschinensicht ist sie es nicht mehr: Dort stünde der Maschinenname zweimal
   * untereinander, und der Leser sucht den Unterschied. Das `aria-label` bleibt
   * unberührt bei `label` — es muss die Sicht eindeutig benennen, auch wenn
   * mehrere davon auf einer Seite stehen.
   */
  heading?: string;
}) {
  const online = useOnline();
  const { phase, trigger, busy, versuch } = usePrediction({ machineId, autoload: true });
  // HITL-Entscheidung lokal je Empfehlung (auditierbar; kein Backend-Schreibpfad).
  const [decided, setDecided] = useState<Record<number, DecisionRecord>>({});

  function renderResult(pair: PredictionPair, stampedAt: string) {
    const result = assemblePredictionCard(pair.prediction, pair.recommendation);
    if (!result.ok) {
      // Negativ-Guard greift: nie eine vorbehaltlose/widersprüchliche Karte.
      return (
        <Notice tone="caveat" role="alert">
          {ASSEMBLE_FAILURE_TEXT[result.reason]}
        </Notice>
      );
    }
    const { card } = result;
    return (
      <ResultWithProvenance
        freshness="cached"
        stampedAt={stampedAt}
        aiGenerated
        caveat
        basis={`Datenbasis: ${dataRegimeLabel(card.caveat.dataRegime)}`}
      >
        <ConfidenceCaveatCard
          card={card}
          roleView={roleView}
          decided={decided[card.recommendationId] ?? null}
          onDecide={
            roleView.canDecide
              ? (disposition: DecisionDisposition, reason: string | null) => {
                  const record = buildDecisionRecord(card, disposition, reason, new Date().toISOString());
                  setDecided((map) => ({ ...map, [card.recommendationId]: record }));
                }
              : undefined
          }
        />
      </ResultWithProvenance>
    );
  }

  const previous = previousResult(phase);

  let body: React.ReactNode;
  if (phase.kind === "processing") {
    body = (
      <div className="flex flex-col gap-4">
        <NamedProcessingState message={processingMessage(versuch)} />
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
    // idle
    body = previous ? (
      renderResult(previous.data, previous.stampedAt)
    ) : (
      <Notice tone="muted" role="status">
        {roleView.canTrigger
          ? "Noch keine Vorhersage — fordern Sie eine an."
          : "Noch keine Erkenntnis vorhanden."}
      </Notice>
    );
  }

  return (
    <section className="flex flex-col gap-4" aria-label={`Ausfallvorhersage — ${label}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-h2 text-fg-primary">{heading ?? label}</h2>
        {roleView.canTrigger ? (
          <TriggerButton
            label="Vorhersage anfordern"
            busyLabel="Vorhersage läuft …"
            busy={busy}
            disabledReason={
              online ? null : "Offline — Erkenntnis nicht abrufbar (Stand siehe Stempel)"
            }
            onTrigger={trigger}
          />
        ) : null}
      </div>
      {body}
    </section>
  );
}
