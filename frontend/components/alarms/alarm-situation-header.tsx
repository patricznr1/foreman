// ============================================================
//  FOREMAN Frontend — components/alarms/alarm-situation-header.tsx
//  Zweck: Das Alarm-Lagebild als reiner, wiederverwendbarer Kopf (Studie §4C):
//         Prioritäts-Zähler je Tier + „Häufigste Quellen" (Maschinen mit den
//         meisten offenen Alarmen). Genutzt vom Manager-Aggregat (AlarmAggregate)
//         UND als Überblicks-Kopf über der vollen Manager-Liste — Überblick PLUS
//         Detail, statt Aggregat-Sackgasse (§21.9 manager-Vollzugriff).
//  Architektur-Einordnung: Reine Präsentation (Schicht 3). Prop-getrieben,
//         transport-agnostisch testbar.
// ============================================================
"use client";

import type { FleetOverviewOut } from "@/lib/api/contracts";
import { countByPriorityFromOverview } from "@/lib/alarms/counts";
import { PRIORITY_LABEL, PRIORITY_ORDER } from "@/lib/alarms/priority";
import { cx } from "@/lib/ui/cx";
import { PRIORITY_TEXT } from "./alarm-styles";

export interface AlarmSituationHeaderProps {
  /** Das overview-Aggregat (live). Fehlt es (noch), wird der Kopf ausgelassen. */
  overview: FleetOverviewOut | undefined;
}

/** Lagebild: Zähler je Prioritäts-Tier + häufigste Quellen (Top-5 offene). */
export function AlarmSituationHeader({ overview }: AlarmSituationHeaderProps) {
  if (!overview) {
    return null;
  }
  const counts = countByPriorityFromOverview(overview);
  const topSources = [...overview.machines]
    .filter((machine) => machine.open_alarm_count > 0)
    .sort((a, b) => b.open_alarm_count - a.open_alarm_count)
    .slice(0, 5);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {PRIORITY_ORDER.map((priority) => (
          <div key={priority} className="rounded-lg border border-line-subtle bg-surface-raised p-4">
            <div className={cx("text-display font-semibold tabular-nums", PRIORITY_TEXT[priority])}>
              {counts[priority]}
            </div>
            <div className="text-caption text-fg-secondary">{PRIORITY_LABEL[priority]}</div>
          </div>
        ))}
      </div>

      <div>
        <h2 className="mb-2 text-body-l font-medium text-fg-primary">Häufigste Quellen</h2>
        {topSources.length === 0 ? (
          <p className="text-body text-fg-muted">Keine offenen Alarme — Anlage ruhig.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {topSources.map((machine) => (
              <li
                key={machine.id}
                className="flex items-center justify-between rounded-md border border-line-subtle bg-surface-raised px-3 py-2"
              >
                <span className="text-body text-fg-primary">{machine.label}</span>
                <span className="text-body tabular-nums text-fg-secondary">
                  {machine.open_alarm_count} offen
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
