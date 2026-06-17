// ============================================================
//  FOREMAN Frontend — components/memory/memory-view.tsx
//  Zweck: Der Einstieg in die Gedächtnis-Suche (Sektion H, Studie §4H). Bindet das
//         GETEILTE On-Demand-Muster (Trigger → benannter Zustand → Ergebnis mit
//         Herkunft) an die Trefferliste. Fünf Pflichtzustände + Degradation:
//         offline → Suche deaktiviert mit Grund, die zuletzt gefundenen Fälle
//         bleiben mit Stand sichtbar (kein Leerlaufen). Rollen-Varianten ohne
//         bedingte Hooks (roleView wird durchgereicht). Herkunft EHRLICH: die Suche
//         ist Abruf echter vergangener Notizen, KEINE KI-Generierung — der Stempel
//         trägt aiGenerated=false und keinen Vorbehalt; das Ergebnis ist ein
//         Retrieval-Snapshot mit Stand (darum freshness="cached", nie ein Live-Puls).
//         Nur ein FRISCH geholtes Ergebnis sagt die Live-Region an (announce). Read-only.
//  Architektur-Einordnung: Sektions-Orchestrierung (Schicht 2, client).
// ============================================================
"use client";

import { type ReactNode, useEffect } from "react";
import { NamedProcessingState, ResultWithProvenance } from "@/components/ondemand";
import type { CurrentUser } from "@/lib/api/contracts";
import { previousResult } from "@/lib/ondemand/machine";
import { useOnline } from "@/lib/ondemand/use-online";
import { memoryRoleView } from "@/lib/memory/roles";
import type { MemorySearchResult } from "@/lib/memory/types";
import { useMemorySearch } from "@/lib/memory/use-memory-search";
import { MemoryResultList } from "./memory-result-list";
import { MemorySearchBar } from "./memory-search-bar";

const PROCESSING_MESSAGE = "Suche nach ähnlichen Fällen im Gedächtnis der Halle …";

const OFFLINE_REASON =
  "Offline — neue Suche nicht möglich (zuletzt gefundene Fälle siehe Stand am Ergebnis)";

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
    if (initial) {
      search(initial, { machineId: null });
    }
  }, [initialQuery, search]);

  // `announce`: nur ein FRISCH geholtes Ergebnis sagt die Live-Region an — ein aus
  // dem Cache rehydriertes oder degradiertes Ergebnis bleibt still (kein alter Stand).
  function renderResult(result: MemorySearchResult, stampedAt: string, announce: boolean) {
    return (
      <ResultWithProvenance
        freshness="cached"
        stampedAt={stampedAt}
        aiGenerated={false}
        caveat={false}
        basis="aus den Schichtberichten der Halle"
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
        Noch keine Suche — beschreiben Sie eine Situation, um ähnliche Fälle zu finden.
      </Notice>
    );
  }

  return (
    <section className="flex flex-col gap-5" aria-label="Gedächtnis und Verknüpfung">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-fg-primary">Gedächtnis</h1>
        <p className="max-w-prose text-body text-fg-secondary">
          Hatten wir das schon mal — irgendwo, an irgendeiner Maschine, in irgendeiner Schicht?
        </p>
      </div>
      <MemorySearchBar
        defaultQuery={initialQuery}
        onSubmit={(query, machineId) => search(query, { machineId })}
        busy={busy}
        canFilter={roleView.canFilter}
        machines={user.assigned_machine_ids}
        disabledReason={online ? null : OFFLINE_REASON}
      />
      {body}
    </section>
  );
}
