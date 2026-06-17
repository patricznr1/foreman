// ============================================================
//  FOREMAN Frontend — components/capture/context-suggestions.tsx
//  Zweck: Die dezente Brücke zu H (Studie §4J): frühere Fälle AN DIESER MASCHINE
//         anbieten — Vorschlag, KEIN Pop-up-Zwang. OPT-IN (§8-Datensparsamkeit):
//         der Entwurfstext geht erst auf eine BEWUSSTE Geste (Button) als Such-Query
//         raus, nie passiv beim Tippen. Abruf echter Notizen, KEINE Generierung →
//         ProvenanceStamp aiGenerated=false. Hallensprache, kein interner Begriff,
//         kein Prozentwert. Autor maskiert (#hex6). Wegklappbar.
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3, client).
// ============================================================
"use client";

import { useState } from "react";
import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import { useContextSuggestions } from "@/lib/capture/use-context-suggestions";
import { maskPseudonym } from "@/lib/ui/pii";

export interface ContextSuggestionsProps {
  text: string;
  machineId: number | null;
  enabled: boolean;
}

function formatDay(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function ContextSuggestions({ text, machineId, enabled }: ContextSuggestionsProps) {
  const { phase, search, busy, canSearch } = useContextSuggestions(text, machineId, enabled);
  const [dismissed, setDismissed] = useState(false);

  // Nichts möglich (keine Maschine / zu kurz / offline) und noch nichts gesucht → ruhen.
  if (dismissed || (!canSearch && phase.kind === "idle")) {
    return null;
  }

  // Opt-in: bewusster Anstoß, BEVOR der Entwurf als Such-Query das Gerät verlässt.
  if (phase.kind === "idle") {
    return (
      <button
        type="button"
        onClick={search}
        disabled={busy}
        className="touch-target inline-flex w-fit items-center gap-2 rounded-lg border border-line-subtle bg-surface-raised px-4 text-caption text-fg-secondary"
      >
        <span aria-hidden="true" className="text-fg-muted">
          ↻
        </span>
        Schon mal hier gewesen? Ähnliche Notizen an dieser Maschine ansehen
      </button>
    );
  }

  if (phase.kind === "processing") {
    return (
      <p role="status" className="text-caption text-fg-muted">
        Suche nach ähnlichen Fällen an dieser Maschine …
      </p>
    );
  }

  if (phase.kind === "error") {
    return (
      <p className="text-caption text-fg-muted">Vorschläge gerade nicht abrufbar.</p>
    );
  }

  const hits = phase.result.data;
  if (hits.length === 0) {
    return (
      <p className="text-caption text-fg-muted">
        Keine ähnlichen früheren Notizen an dieser Maschine gefunden.
      </p>
    );
  }

  return (
    <aside
      aria-label="Ähnliche frühere Notizen an dieser Maschine"
      className="flex flex-col gap-2 rounded-lg border border-line-subtle bg-surface-raised p-3"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-caption font-semibold text-fg-secondary">
          Frühere Notizen an dieser Maschine
        </h3>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          aria-label="Vorschläge ausblenden"
          className="touch-target inline-flex items-center rounded-md px-2 text-caption text-fg-muted"
        >
          ausblenden
        </button>
      </div>
      <ul className="flex flex-col gap-2">
        {hits.map((note) => {
          const author = maskPseudonym(note.author);
          const day = formatDay(note.created_at);
          return (
            <li key={note.id} className="text-caption text-fg-secondary">
              <span className="line-clamp-2 text-fg-primary">{note.text}</span>
              <span className="text-fg-muted">
                {[day, note.shift, author].filter(Boolean).join(" · ")}
              </span>
            </li>
          );
        })}
      </ul>
      <ProvenanceStamp freshness="cached" stampedAt={phase.result.stampedAt} aiGenerated={false} />
      <span className="text-caption text-fg-muted">aus früheren Schichtnotizen der Halle</span>
    </aside>
  );
}
