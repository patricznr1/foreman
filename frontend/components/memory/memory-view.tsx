// ============================================================
//  FOREMAN Frontend — components/memory/memory-view.tsx
//  Zweck: Der Einstieg in das ARCHIV (Paket 1c) — die WÖRTLICHE Suche über abgelegte
//         Schichtberichte, Wartungsprotokolle und Alarme. Ehrlich benannt: es findet,
//         was im Wortlaut da ist; das intelligente „Hatten wir das schon mal" ist
//         bewusst NICHT hier (folgt mit echter Substanz). Bindet das GETEILTE
//         On-Demand-Muster (Trigger → benannter Zustand → Ergebnis mit Herkunft).
//         Degradation: offline → Suche deaktiviert mit Grund, die zuletzt gefundenen
//         Treffer bleiben mit Stand sichtbar. Rollen-Varianten ohne bedingte Hooks
//         (roleView durchgereicht). Herkunft EHRLICH: Abruf, KEINE KI-Generierung
//         (aiGenerated=false, kein Vorbehalt; freshness="cached"). Read-only.
//  Architektur-Einordnung: Sektions-Orchestrierung (Schicht 2, client).
// ============================================================
"use client";

import { type ReactNode, useEffect } from "react";
import { NamedProcessingState, ResultWithProvenance } from "@/components/ondemand";
import type { CurrentUser } from "@/lib/api/contracts";
import { previousResult } from "@/lib/ondemand/machine";
import { useOnline } from "@/lib/ondemand/use-online";
import { memoryRoleView } from "@/lib/memory/roles";
import { SOURCE_LABEL } from "@/lib/memory/source";
import type { ArchiveSearchResult, SourceType } from "@/lib/memory/types";
import { useMemorySearch } from "@/lib/memory/use-memory-search";
import { MemoryResultList } from "./memory-result-list";
import { MemorySearchBar } from "./memory-search-bar";

const PROCESSING_MESSAGE = "Durchsucht das Archiv nach dem Stichwort …";

const OFFLINE_REASON =
  "Offline — neue Suche nicht möglich (zuletzt gefundene Treffer siehe Stand am Ergebnis)";

/** Herkunfts-Basis aus den tatsächlich durchsuchten Quellen (ehrlich, §E). */
function basisText(sources: SourceType[]): string {
  if (sources.length === 0) {
    return "aus dem Archiv";
  }
  return `aus dem Archiv (${sources.map((source) => SOURCE_LABEL[source]).join(", ")})`;
}

/** Ruhiger Hinweis (Fehler/leer) — Hallensprache, kein Alarm-Rot. */
function Notice({
  tone,
  role,
  children,
}: {
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

export function MemoryView({ user, initialQuery }: { user: CurrentUser; initialQuery?: string }) {
  const roleView = memoryRoleView(user.role);
  const online = useOnline();
  const { phase, search, busy } = useMemorySearch();

  // Deep-Link aus der Befehlsleiste (?q=…) löst beim Eintritt genau eine Suche aus.
  useEffect(() => {
    const initial = initialQuery?.trim();
    if (initial && online) {
      search(initial, { machineId: null });
    }
  }, [initialQuery, online, search]);

  // `announce`: nur ein FRISCH geholtes Ergebnis sagt die Live-Region an — ein aus
  // dem Cache rehydriertes oder degradiertes Ergebnis bleibt still (kein alter Stand).
  function renderResult(result: ArchiveSearchResult, stampedAt: string, announce: boolean) {
    return (
      <ResultWithProvenance
        freshness="cached"
        stampedAt={stampedAt}
        aiGenerated={false}
        caveat={false}
        basis={basisText(result.sources)}
      >
        <MemoryResultList result={result} roleView={roleView} announce={announce} />
      </ResultWithProvenance>
    );
  }

  const previous = previousResult(phase);

  let body: ReactNode;
  if (phase.kind === "processing") {
    body = (
      <div className="flex flex-col gap-4">
        <NamedProcessingState message={PROCESSING_MESSAGE} />
        {previous ? renderResult(previous.data, previous.stampedAt, false) : null}
      </div>
    );
  } else if (phase.kind === "result") {
    body = renderResult(phase.result.data, phase.result.stampedAt, true);
  } else if (phase.kind === "error") {
    body = (
      <div className="flex flex-col gap-4">
        <Notice tone="caveat" role="alert">
          {phase.message}
        </Notice>
        {previous ? renderResult(previous.data, previous.stampedAt, false) : null}
      </div>
    );
  } else {
    body = previous ? (
      renderResult(previous.data, previous.stampedAt, false)
    ) : (
      <Notice tone="muted" role="status">
        Noch keine Suche — geben Sie ein Stichwort ein, um die abgelegten Berichte zu durchsuchen.
      </Notice>
    );
  }

  return (
    <section className="flex flex-col gap-5" aria-label="Archiv">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-fg-primary">Archiv</h1>
        <p className="max-w-prose text-body text-fg-secondary">
          Durchsucht abgelegte Schichtberichte, Wartungsprotokolle und Alarme im Wortlaut.
        </p>
      </div>
      <MemorySearchBar
        defaultQuery={initialQuery}
        onSubmit={(query, machineId, sources) => search(query, { machineId, sources })}
        busy={busy}
        canFilter={roleView.canFilter}
        machines={user.assigned_machine_ids}
        disabledReason={online ? null : OFFLINE_REASON}
      />
      {body}
    </section>
  );
}
