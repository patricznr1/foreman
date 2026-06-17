// ============================================================
//  FOREMAN Frontend — components/ondemand/trigger-button.tsx
//  Zweck: Der GETEILTE On-Demand-Auslöser (Studie §3.2): ein großer, handschuh-
//         sicherer Knopf, der eine Erkenntnis anfordert („Vorhersage anfordern",
//         „Kette rekonstruieren", „Szenario rechnen"). Bei Degradation (offline)
//         sichtbar deaktiviert MIT GRUND (§3.2) — nie stumm tot. Keine Dringlich-
//         keits-Animation (§5.6). E und D/F/G/H teilen sich diesen Baustein.
//  Architektur-Einordnung: On-Demand-Atom (Schicht 2). Rein präsentational.
// ============================================================
"use client";

import { cx } from "@/lib/ui/cx";

export interface TriggerButtonProps {
  /** Auslöser-Label in Hallensprache (z. B. „Vorhersage anfordern"). */
  label: string;
  onTrigger: () => void;
  /** Läuft gerade — Knopf gesperrt, Label wechselt auf busyLabel. */
  busy?: boolean;
  busyLabel?: string;
  /**
   * Wenn gesetzt: Knopf deaktiviert UND der Grund wird sichtbar genannt
   * (offline, keine Rolle, keine Route). Null/undefined = bedienbar.
   */
  disabledReason?: string | null;
  className?: string;
}

export function TriggerButton({
  label,
  onTrigger,
  busy = false,
  busyLabel,
  disabledReason = null,
  className,
}: TriggerButtonProps) {
  const disabled = busy || disabledReason !== null;
  const shownLabel = busy && busyLabel ? busyLabel : label;

  return (
    <div className={cx("flex flex-col gap-2", className)}>
      <button
        type="button"
        onClick={onTrigger}
        disabled={disabled}
        aria-disabled={disabled}
        aria-describedby={disabledReason !== null ? "trigger-disabled-reason" : undefined}
        className={cx(
          "inline-flex min-h-[var(--touch-safety)] items-center justify-center gap-2",
          "rounded-lg px-6 text-body-l font-medium",
          "border border-line-strong bg-surface-overlay text-fg-primary",
          "transition-colors duration-[var(--motion-base)] motion-reduce:transition-none",
          "hover:bg-surface-raised",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring",
          "disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-surface-overlay",
        )}
      >
        {shownLabel}
      </button>
      {disabledReason !== null ? (
        <p id="trigger-disabled-reason" className="text-caption text-note-caveat">
          {disabledReason}
        </p>
      ) : null}
    </div>
  );
}
