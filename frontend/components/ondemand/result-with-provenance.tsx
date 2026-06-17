// ============================================================
//  FOREMAN Frontend — components/ondemand/result-with-provenance.tsx
//  Zweck: Der GETEILTE Ergebnis-Rahmen (Studie §3.2): jedes On-Demand-Ergebnis
//         trägt seinen Herkunftsstempel (Stand, Datenbasis) — der AI-Act-
//         Transparenzanker an erzeugter KI-Erkenntnis. E und D/F/G/H stempeln
//         ihr Ergebnis identisch. Der Stempel ist Pflicht, nicht optional.
//  Architektur-Einordnung: On-Demand-Molekül (Schicht 2). Rein präsentational.
// ============================================================
"use client";

import type { ReactNode } from "react";
import { type Freshness, ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import { cx } from "@/lib/ui/cx";

export interface ResultWithProvenanceProps {
  children: ReactNode;
  freshness: Freshness;
  /** Zeitpunkt des Stands. */
  stampedAt?: Date | string | null;
  /** Als KI-erzeugt kennzeichnen (AI-Act-Transparenz). */
  aiGenerated?: boolean;
  /** Vorbehalt-Signalfarbe am Stempel (ruhig, kein Alarm). */
  caveat?: boolean;
  /** Kurzhinweis zur Datenbasis (Hallensprache), neben dem Stempel. */
  basis?: string;
  className?: string;
}

export function ResultWithProvenance({
  children,
  freshness,
  stampedAt,
  aiGenerated = false,
  caveat = false,
  basis,
  className,
}: ResultWithProvenanceProps) {
  return (
    <div className={cx("flex flex-col gap-3", className)}>
      {children}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line-subtle pt-3">
        <ProvenanceStamp
          freshness={freshness}
          stampedAt={stampedAt}
          aiGenerated={aiGenerated}
          caveat={caveat}
        />
        {basis ? <span className="text-caption text-fg-muted">{basis}</span> : null}
      </div>
    </div>
  );
}
