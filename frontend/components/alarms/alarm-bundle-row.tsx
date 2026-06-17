// ============================================================
//  FOREMAN Frontend — components/alarms/alarm-bundle-row.tsx
//  Zweck: Flood-Bündel-Zeile (Studie §4C). Zeigt „12 Alarme · gemeinsame Quelle
//         Linie 3" statt 12 Einzelzeilen — auf-/zuklappbar (die Mitglieder erscheinen
//         dann als eingerückte Zeilen darunter). Prioritäts-Kodierung wie die Zeile;
//         kein Puls auf dem Bündel selbst (der Puls bleibt der Einzelzeile vorbehalten).
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3, client). Rein präsentational.
// ============================================================
"use client";

import type { AlarmBundle } from "@/lib/alarms/types";
import { cx } from "@/lib/ui/cx";
import { PRIORITY_BORDER, PRIORITY_CHIP, PRIORITY_DOT, railWidth } from "./alarm-styles";

export interface AlarmBundleRowProps {
  bundle: AlarmBundle;
  expanded: boolean;
  onToggle: (key: string) => void;
}

export function AlarmBundleRow({ bundle, expanded, onToggle }: AlarmBundleRowProps) {
  const { priority } = bundle.representative;
  return (
    <div
      className={cx(
        "flex h-full items-center gap-3 bg-surface-raised pr-2 pl-3",
        railWidth(priority),
        PRIORITY_BORDER[priority],
      )}
    >
      <span
        aria-hidden="true"
        className={cx(
          "h-3 w-3 shrink-0 rounded-full",
          PRIORITY_DOT[priority],
          // 1-Hz-Puls auch am geschlossenen Bündel, wenn ein Mitglied unquittiert-kritisch ist.
          bundle.hasActiveCriticalPulse && "attention-pulse",
        )}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-body font-semibold text-fg-primary">{bundle.count} Alarme</span>
          <span
            className={cx("shrink-0 rounded px-1.5 text-caption font-semibold", PRIORITY_CHIP[priority])}
          >
            {bundle.representative.priorityLabel}
          </span>
        </div>
        <div className="truncate text-caption text-fg-secondary">{bundle.sourceLabel}</div>
      </div>
      <button
        type="button"
        onClick={() => onToggle(bundle.key)}
        aria-expanded={expanded}
        className="touch-target inline-flex items-center rounded-md border border-line-strong px-3 text-body text-fg-primary"
      >
        {expanded ? "Einklappen" : "Aufklappen"}
      </button>
    </div>
  );
}
