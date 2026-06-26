// ============================================================
//  FOREMAN Frontend — components/memory/memory-search-bar.tsx
//  Zweck: Die Stichwort-Suchzeile des ARCHIVS (Paket 1c) — ein schmales Wortlaut-
//         Feld mit Lupe ("durchsucht abgelegte Berichte im Wortlaut"), KEINE
//         "Situation beschreiben"-Maske (die gehört zum späteren intelligenten
//         Verknüpfen). Absenden = On-Demand-Auslöser (Studie §3.2). Filter
//         (Schichtleiter/Techniker/Manager): optionaler Maschinen-Filter +
//         drei Quellen-Toggles (Schichtnotizen/Wartung/Alarme, Vorbild Sensor-
//         Toggle). Offline: Absenden deaktiviert MIT GRUND. Read-only.
//  Architektur-Einordnung: Sektions-Molekül (Schicht 2, client).
// ============================================================
"use client";

import { type FormEvent, useEffect, useId, useState } from "react";
import type { SourceType } from "@/lib/memory/types";
import { cx } from "@/lib/ui/cx";

/** Quellen-Optionen in kanonischer Reihenfolge (auch fürs sources[]-Serialisieren). */
const SOURCE_OPTIONS: { value: SourceType; label: string }[] = [
  { value: "note", label: "Schichtnotizen" },
  { value: "maintenance", label: "Wartung" },
  { value: "alarm", label: "Alarme" },
];

export interface MemorySearchBarProps {
  defaultQuery?: string;
  /** Absenden der Suche (Trigger) — query + Maschinen-Filter + aktive Quellen. */
  onSubmit: (query: string, machineId: number | null, sources: SourceType[]) => void;
  busy: boolean;
  /** Filter (Maschine + Quellen-Toggles) sichtbar (Schichtleiter/Techniker/Manager)? */
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
  const [active, setActive] = useState<Set<SourceType>>(
    () => new Set<SourceType>(["note", "maintenance", "alarm"]),
  );
  const reasonId = useId();
  const noSources = active.size === 0;
  const disabled = busy || disabledReason !== null || noSources;

  // Ein Deep-Link-Wechsel (?q=…) ändert defaultQuery von außen (z. B. über die
  // Befehlsleiste) — dann das Eingabefeld nachführen, damit es zur Suche passt.
  useEffect(() => {
    setQuery(defaultQuery);
  }, [defaultQuery]);

  function toggleSource(value: SourceType): void {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(value)) {
        next.delete(value);
      } else {
        next.add(value);
      }
      return next;
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (disabled) {
      return;
    }
    const sources = SOURCE_OPTIONS.map((option) => option.value).filter((value) =>
      active.has(value),
    );
    onSubmit(query, machineId, sources);
  }

  return (
    <form
      onSubmit={handleSubmit}
      role="search"
      aria-label="Archiv durchsuchen"
      className="flex flex-col gap-3"
    >
      <label htmlFor="archive-query" className="text-caption text-fg-muted">
        Stichwort — durchsucht abgelegte Berichte im Wortlaut
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative w-full">
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted"
          >
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="9" cy="9" r="6" />
              <line x1="14" y1="14" x2="18" y2="18" strokeLinecap="round" />
            </svg>
          </span>
          <input
            id="archive-query"
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="z. B. Fett, Beleuchtung, Lager"
            aria-describedby={disabledReason !== null ? reasonId : undefined}
            className="min-h-[var(--touch-safety)] w-full rounded-lg border border-line-strong bg-surface-overlay pl-10 pr-4 text-body-l text-fg-primary placeholder:text-fg-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          />
        </div>
        <button
          type="submit"
          disabled={disabled}
          aria-disabled={disabled}
          className="inline-flex min-h-[var(--touch-safety)] items-center justify-center rounded-lg border border-line-strong bg-surface-overlay px-6 text-body-l font-medium text-fg-primary transition-colors duration-[var(--motion-base)] motion-reduce:transition-none hover:bg-surface-raised focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-surface-overlay"
        >
          {busy ? "Suche läuft …" : "Suchen"}
        </button>
      </div>
      {disabledReason !== null ? (
        <p id={reasonId} className="text-caption text-note-caveat">
          {disabledReason}
        </p>
      ) : null}
      {canFilter ? (
        <div className="flex flex-col gap-3">
          <div role="group" aria-label="Quellen" className="flex flex-wrap items-center gap-2">
            {SOURCE_OPTIONS.map((option) => {
              const isActive = active.has(option.value);
              return (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => toggleSource(option.value)}
                  className={cx(
                    "touch-target rounded-md border px-3 text-body",
                    isActive
                      ? "border-line-strong text-fg-primary"
                      : "border-line-subtle text-fg-secondary",
                  )}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            {machines.length > 0 ? (
              <div className="flex items-center gap-2">
                <label htmlFor="archive-machine" className="text-caption text-fg-muted">
                  Maschine
                </label>
                <select
                  id="archive-machine"
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
            {noSources ? (
              <span className="text-caption text-note-caveat">Mindestens eine Quelle wählen</span>
            ) : null}
          </div>
        </div>
      ) : null}
    </form>
  );
}
