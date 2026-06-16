// ============================================================
//  FOREMAN Frontend — components/atoms/status-indicator.tsx
//  Zweck: Das meistgenutzte Atom (§5.5) — FCSM-Zustand MEHRKANALIG: Farbe
//         (state-* Token) + Form/Label (FCSM-Kürzel) + Klartext-Label. Nie nur
//         Farbe (Prinzip 3/8). Größen S/M/L; optionaler 1-Hz-Aufmerksamkeitspuls
//         ausschließlich für unquittiert-kritische Zustände (§5.6).
//  Architektur-Einordnung: Atom (Schicht 2). Rein präsentational, transport-frei.
// ============================================================
import { cx } from "@/lib/ui/cx";
import { FCSM_LABEL, FCSM_LETTER, type Fcsm } from "@/lib/ui/wording";

export type StatusIndicatorSize = "s" | "m" | "l";

export interface StatusIndicatorProps {
  status: Fcsm;
  /** Override für das Klartext-Label (Default: Hallensprache-Label des Zustands). */
  label?: string;
  size?: StatusIndicatorSize;
  showLabel?: boolean;
  /** Nur für unquittiert-kritisch (ISA-18.2: Blinken = unquittiert, nicht Severity). */
  pulse?: boolean;
  className?: string;
}

// Statische Klassen-Maps, damit der Tailwind-Scanner sie findet (kein Template-String).
const FILL: Record<Fcsm, string> = {
  failure: "bg-state-failure",
  check: "bg-state-check",
  outofspec: "bg-state-outofspec",
  maintenance: "bg-state-maintenance",
  ok: "bg-state-ok",
};

const BADGE: Record<StatusIndicatorSize, string> = {
  s: "h-7 min-w-7 px-1 text-caption",
  m: "h-9 min-w-9 px-1.5 text-body",
  l: "h-12 min-w-12 px-2 text-body-l",
};

const LABEL: Record<StatusIndicatorSize, string> = {
  s: "text-caption",
  m: "text-body",
  l: "text-body-l",
};

export function StatusIndicator({
  status,
  label,
  size = "m",
  showLabel = true,
  pulse = false,
  className,
}: StatusIndicatorProps) {
  const text = label ?? FCSM_LABEL[status];
  return (
    <span className={cx("inline-flex items-center gap-2", className)} role="img" aria-label={text}>
      <span
        aria-hidden="true"
        className={cx(
          "inline-flex items-center justify-center rounded-md font-mono font-semibold text-fg-on-accent",
          FILL[status],
          BADGE[size],
          pulse && "attention-pulse",
        )}
      >
        {FCSM_LETTER[status]}
      </span>
      {showLabel ? <span className={cx("text-fg-primary", LABEL[size])}>{text}</span> : null}
    </span>
  );
}
