// ============================================================
//  FOREMAN Frontend — components/platform/audit-filters.tsx
//  Zweck: Die Filterleiste der Audit-Tabelle (Studie §4I) gegen die REALEN
//         Query-Parameter (§22.1): Aktionsart, Zielart/-ID, Akteur, Maschine,
//         Zeitraum, Seitengröße. Bewusstes Anwenden (kein Fetch pro Tastendruck):
//         der Entwurf wird lokal gehalten und erst per „Anwenden" übernommen
//         (Seite springt dann auf 0). KEINE Mutations-Aktion — reine Lese-Steuerung.
//  Architektur-Einordnung: Steuer-Komponente (Schicht 2, client).
// ============================================================
"use client";

import { useState } from "react";
import {
  activeFilterCount,
  AUDIT_ACTIONS,
  AUDIT_DEFAULT_PAGE_SIZE,
  emptyAuditFilter,
  type AuditFilter,
} from "@/lib/platform/audit-filter";

const PAGE_SIZES = [25, 50, 100, 200] as const;

const FIELD =
  "rounded-md border border-line-subtle bg-surface-canvas px-2 py-1.5 text-body text-fg-primary";
const LABEL = "flex flex-col gap-1 text-caption text-fg-secondary";

function parseOptionalInt(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isInteger(parsed) ? parsed : null;
}

export interface AuditFiltersProps {
  initial: AuditFilter;
  onApply: (filter: AuditFilter) => void;
}

export function AuditFilters({ initial, onApply }: AuditFiltersProps) {
  const [draft, setDraft] = useState<AuditFilter>(initial);

  function update<K extends keyof AuditFilter>(key: K, value: AuditFilter[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function apply() {
    // Neue Filter → zurück auf die erste (jüngste) Seite.
    onApply({ ...draft, offset: 0 });
  }

  function reset() {
    const cleared = emptyAuditFilter();
    setDraft(cleared);
    onApply(cleared);
  }

  return (
    <form
      className="flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised p-4"
      onSubmit={(event) => {
        event.preventDefault();
        apply();
      }}
      aria-label="Audit-Filter"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className={LABEL}>
          Aktionsart
          <select
            className={FIELD}
            value={draft.actionType ?? ""}
            onChange={(e) =>
              update("actionType", e.target.value === "" ? null : (e.target.value as AuditFilter["actionType"]))
            }
          >
            <option value="">alle</option>
            {AUDIT_ACTIONS.map((action) => (
              <option key={action} value={action}>
                {action}
              </option>
            ))}
          </select>
        </label>

        <label className={LABEL}>
          Zielart
          <input
            className={FIELD}
            type="text"
            value={draft.targetKind}
            placeholder="z. B. alarm, explanation"
            onChange={(e) => update("targetKind", e.target.value)}
          />
        </label>

        <label className={LABEL}>
          Ziel-ID
          <input
            className={FIELD}
            type="number"
            inputMode="numeric"
            value={draft.targetId ?? ""}
            onChange={(e) => update("targetId", parseOptionalInt(e.target.value))}
          />
        </label>

        <label className={LABEL}>
          Akteur (Token)
          <input
            className={FIELD}
            type="text"
            value={draft.actor}
            placeholder="pseudonymer Token"
            onChange={(e) => update("actor", e.target.value)}
          />
        </label>

        <label className={LABEL}>
          Maschine
          <input
            className={FIELD}
            type="number"
            inputMode="numeric"
            value={draft.machineId ?? ""}
            onChange={(e) => update("machineId", parseOptionalInt(e.target.value))}
          />
        </label>

        <label className={LABEL}>
          Seitengröße
          <select
            className={FIELD}
            value={draft.limit}
            onChange={(e) => update("limit", Number(e.target.value) || AUDIT_DEFAULT_PAGE_SIZE)}
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>

        <label className={LABEL}>
          ab (Zeitpunkt)
          <input
            className={FIELD}
            type="datetime-local"
            value={draft.since}
            onChange={(e) => update("since", e.target.value)}
          />
        </label>

        <label className={LABEL}>
          bis (Zeitpunkt)
          <input
            className={FIELD}
            type="datetime-local"
            value={draft.until}
            onChange={(e) => update("until", e.target.value)}
          />
        </label>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          className="touch-target rounded-md bg-surface-overlay px-4 text-body font-medium text-fg-primary hover:bg-surface-canvas"
        >
          Anwenden
        </button>
        <button
          type="button"
          onClick={reset}
          className="touch-target rounded-md px-4 text-body text-fg-secondary hover:bg-surface-overlay"
        >
          Zurücksetzen
        </button>
        <span className="text-caption text-fg-muted">
          {activeFilterCount(draft) === 0
            ? "keine Filter aktiv"
            : `${activeFilterCount(draft)} Filter aktiv`}
        </span>
      </div>
    </form>
  );
}
