// ============================================================
//  FOREMAN Frontend — components/memory/memory-search-bar.tsx
//  Zweck: Die natürlichsprachliche Suchzeile (Studie §4H: das einladende Tor zum
//         Raum, bewusst prominent). Eingabe ist eine Beschreibung in Alltagssprache,
//         keine Filtermaske. Absenden = On-Demand-Auslöser (Studie §3.2). Optionaler
//         Maschinen-Filter (realer Backend-Parameter machine_id); breitere Filter
//         (Zeitraum/Bereich) sind ehrlich als folgt markiert. Offline: Absenden
//         deaktiviert MIT GRUND. Read-only — keine Aktorik.
//  Architektur-Einordnung: Sektions-Molekül (Schicht 2, client).
// ============================================================
"use client";

import { type FormEvent, useId, useState } from "react";

export interface MemorySearchBarProps {
  defaultQuery?: string;
  /** Absenden der Suche (Trigger) — query + optionaler Maschinen-Filter. */
  onSubmit: (query: string, machineId: number | null) => void;
  busy: boolean;
  /** Filter-Chips sichtbar (Schichtleiter/Techniker/Manager)? */
  canFilter: boolean;
  /** Zuordenbare Maschinen für den optionalen Filter. */
  machines: number[];
  /** Gesetzt = Absenden gesperrt mit sichtbarem Grund (offline). */
  disabledReason?: string | null;
}

export function MemorySearchBar({
  defaultQuery = "",
  onSubmit,
  busy,
  canFilter,
  machines,
  disabledReason = null,
}: MemorySearchBarProps) {
  const [query, setQuery] = useState(defaultQuery);
  const [machineId, setMachineId] = useState<number | null>(null);
  const reasonId = useId();
  const disabled = busy || disabledReason !== null;

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (disabled) {
      return;
    }
    onSubmit(query, machineId);
  }

  return (
    <form
      onSubmit={handleSubmit}
      role="search"
      aria-label="Gedächtnis durchsuchen"
      className="flex flex-col gap-3"
    >
      <label htmlFor="memory-query" className="text-caption text-fg-muted">
        Beschreiben Sie die Situation
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          id="memory-query"
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="z. B. Lager läuft heiß nach Schichtwechsel"
          aria-describedby={disabledReason !== null ? reasonId : undefined}
          className="min-h-[var(--touch-safety)] w-full rounded-lg border border-line-strong bg-surface-overlay px-4 text-body-l text-fg-primary placeholder:text-fg-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        />
        <button
          type="submit"
          disabled={disabled}
          aria-disabled={disabled}
          className="inline-flex min-h-[var(--touch-safety)] items-center justify-center rounded-lg border border-line-strong bg-surface-overlay px-6 text-body-l font-medium text-fg-primary transition-colors duration-[var(--motion-base)] motion-reduce:transition-none hover:bg-surface-raised focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-surface-overlay"
        >
          {busy ? "Suche läuft …" : "Ähnliche Fälle finden"}
        </button>
      </div>
      {disabledReason !== null ? (
        <p id={reasonId} className="text-caption text-note-caveat">
          {disabledReason}
        </p>
      ) : null}
      {canFilter ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {machines.length > 0 ? (
            <div className="flex items-center gap-2">
              <label htmlFor="memory-machine" className="text-caption text-fg-muted">
                Maschine
              </label>
              <select
                id="memory-machine"
                value={machineId ?? ""}
                onChange={(event) =>
                  setMachineId(event.target.value === "" ? null : Number(event.target.value))
                }
                className="min-h-[var(--touch-min)] rounded-md border border-line-strong bg-surface-overlay px-3 text-body text-fg-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
              >
                <option value="">Alle Maschinen</option>
                {machines.map((id) => (
                  <option key={id} value={id}>
                    Maschine {id}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          <span className="text-caption text-fg-muted">Filter nach Zeitraum und Bereich folgt</span>
        </div>
      ) : null}
    </form>
  );
}
