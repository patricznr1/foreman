// ============================================================
//  FOREMAN Frontend — components/ondemand/named-processing-state.tsx
//  Zweck: Der GETEILTE benannte Verarbeitungszustand (Studie §3.2): KEIN
//         generischer Spinner, sondern ein benannter Fortschritt
//         („werte aktuelle Lage gegen vergangene Verläufe aus…"). Höfliche
//         Live-Region für Screenreader. Ruhiger Puls, der Dringlichkeit NICHT
//         suggeriert und unter reduced-motion stillsteht (§5.6).
//  Architektur-Einordnung: On-Demand-Atom (Schicht 2). Rein präsentational.
// ============================================================
"use client";

import { cx } from "@/lib/ui/cx";

export interface NamedProcessingStateProps {
  /** Was gerade geschieht — in Hallensprache, vom Aufrufer benannt. */
  message: string;
  className?: string;
}

export function NamedProcessingState({ message, className }: NamedProcessingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cx(
        "flex min-h-24 items-center justify-center gap-3 rounded-lg",
        "border border-line-subtle bg-surface-raised p-4 text-body text-fg-secondary",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="inline-block h-2.5 w-2.5 rounded-full bg-fg-muted animate-pulse motion-reduce:animate-none"
      />
      <span>{message}</span>
    </div>
  );
}
