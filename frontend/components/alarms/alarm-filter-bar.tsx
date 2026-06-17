// ============================================================
//  FOREMAN Frontend — components/alarms/alarm-filter-bar.tsx
//  Zweck: Listenkopf (Studie §4C): Prioritäts-Zähler („2 kritisch · 5 hoch · 11
//         mittel") + Drift-Zähler, Filter (Priorität/Drift/Lebenszyklus) und
//         Gruppierung (Priorität/Bereich/Maschine). Die Sicht „atmet" über den
//         Stand-Stempel (ProvenanceStamp) — BEWUSST ohne Blinken: der 1-Hz-Puls
//         bleibt ISA-18.2-konform der unquittiert-kritischen Zeile vorbehalten (§5.6).
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3, client).
// ============================================================
"use client";

import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import { PRIORITY_LABEL, PRIORITY_ORDER } from "@/lib/alarms/priority";
import type { AlarmFilter, GroupMode, LifecycleFilter, PriorityCounts, Priority } from "@/lib/alarms/types";
import { cx } from "@/lib/ui/cx";
import { PRIORITY_TEXT } from "./alarm-styles";

export interface AlarmFilterBarProps {
  counts: PriorityCounts;
  driftCount: number;
  freshness: "live" | "cached";
  stampedAt: Date | null;
  filter: AlarmFilter;
  onFilterChange: (filter: AlarmFilter) => void;
  groupMode: GroupMode;
  onGroupModeChange: (mode: GroupMode) => void;
}

const GROUP_LABEL: Record<GroupMode, string> = {
  priority: "Priorität",
  area: "Bereich",
  machine: "Maschine",
};

const LIFECYCLE_OPTIONS: { value: LifecycleFilter; label: string }[] = [
  { value: "open", label: "Offen" },
  { value: "acknowledged", label: "Quittiert" },
  { value: "cleared", label: "Geklärt" },
  { value: "all", label: "Alle" },
];

function togglePriority(filter: AlarmFilter, priority: Priority): AlarmFilter {
  // Semantik konsistent: leeres Set = „alle aktiv". Ein Klick aus „alle" wählt die
  // Priorität ab (statt nur sie zu zeigen); sind danach wieder alle drin → leeren.
  const priorities =
    filter.priorities.size === 0 ? new Set<Priority>(PRIORITY_ORDER) : new Set(filter.priorities);
  if (priorities.has(priority)) {
    priorities.delete(priority);
  } else {
    priorities.add(priority);
  }
  if (priorities.size === PRIORITY_ORDER.length) {
    return { ...filter, priorities: new Set<Priority>() };
  }
  return { ...filter, priorities };
}

export function AlarmFilterBar({
  counts,
  driftCount,
  freshness,
  stampedAt,
  filter,
  onFilterChange,
  groupMode,
  onGroupModeChange,
}: AlarmFilterBarProps) {
  return (
    <div className="flex flex-col gap-3 border-b border-line-subtle bg-surface-raised p-3">
      {/* Zähler je Priorität + Stand-Stempel (die Sicht atmet). */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-body" aria-live="polite">
          {PRIORITY_ORDER.map((priority) => {
            const value = counts[priority];
            if (value === 0 && (priority === "low" || priority === "journal")) {
              return null;
            }
            return (
              <span key={priority} className="inline-flex items-baseline gap-1">
                <span className={cx("font-semibold tabular-nums", PRIORITY_TEXT[priority])}>
                  {value}
                </span>
                <span className="text-caption text-fg-secondary">
                  {PRIORITY_LABEL[priority].toLowerCase()}
                </span>
              </span>
            );
          })}
          {driftCount > 0 ? (
            <span className="inline-flex items-baseline gap-1">
              <span className="font-semibold tabular-nums text-fg-secondary">{driftCount}</span>
              <span className="text-caption text-fg-secondary">Abweichung</span>
            </span>
          ) : null}
        </div>
        <ProvenanceStamp freshness={freshness} stampedAt={stampedAt} />
      </div>

      {/* Filter + Gruppierung. */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Nach Priorität filtern">
          {PRIORITY_ORDER.map((priority) => {
            const active = filter.priorities.size === 0 || filter.priorities.has(priority);
            return (
              <button
                key={priority}
                type="button"
                aria-pressed={active}
                onClick={() => onFilterChange(togglePriority(filter, priority))}
                className={cx(
                  "touch-target rounded-md px-3 text-caption",
                  active
                    ? "bg-surface-overlay text-fg-primary border border-line-strong"
                    : "text-fg-secondary",
                )}
              >
                {PRIORITY_LABEL[priority]}
              </button>
            );
          })}
        </div>

        <button
          type="button"
          aria-pressed={filter.driftOnly}
          onClick={() => onFilterChange({ ...filter, driftOnly: !filter.driftOnly })}
          className={cx(
            "touch-target rounded-md px-3 text-caption",
            filter.driftOnly
              ? "bg-surface-overlay text-fg-primary border border-line-strong"
              : "text-fg-secondary",
          )}
        >
          Nur Abweichungen
        </button>

        <label className="inline-flex items-center gap-1 text-caption text-fg-secondary">
          Status
          <select
            value={filter.lifecycle}
            onChange={(event) =>
              onFilterChange({ ...filter, lifecycle: event.target.value as LifecycleFilter })
            }
            className="touch-target rounded-md border border-line-subtle bg-surface-overlay px-2 text-body text-fg-primary"
          >
            {LIFECYCLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="ml-auto inline-flex items-center gap-1 text-caption text-fg-secondary">
          Gruppieren
          <select
            value={groupMode}
            onChange={(event) => onGroupModeChange(event.target.value as GroupMode)}
            className="touch-target rounded-md border border-line-subtle bg-surface-overlay px-2 text-body text-fg-primary"
          >
            {(Object.keys(GROUP_LABEL) as GroupMode[]).map((mode) => (
              <option key={mode} value={mode}>
                {GROUP_LABEL[mode]}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
