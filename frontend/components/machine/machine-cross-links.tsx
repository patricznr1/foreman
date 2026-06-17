// ============================================================
//  FOREMAN Frontend — components/machine/machine-cross-links.tsx
//  Zweck: Schnellaktionen/Verbindungen der Maschinen-Detail-Sicht — reine NAVIGATION
//         bzw. menschliche ANFORDERUNG, nie Anlagen-Schaltung (HITL, §4B): Notiz
//         erfassen → J (/capture), Vorhersage anfordern → E (/insights/prediction),
//         Ereigniskette → D (/insights). Noch nicht voll ausgebaute Ziele (J/D) sind
//         graceful (Route existiert als Platzhalter). Rollen-Gating über Props.
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3, client).
// ============================================================
import Link from "next/link";

import { cx } from "@/lib/ui/cx";

export interface MachineCrossLinksProps {
  machineId: number;
  /** Werker/Schichtleiter/Techniker dürfen Notizen erfassen (→ J). */
  canCaptureNote: boolean;
  /** Nur Schichtleiter fordert eine Vorhersage an (→ E, On-Demand). */
  canRequestPrediction: boolean;
  className?: string;
}

const LINK_CLASS =
  "touch-target inline-flex items-center rounded-md border border-line-subtle bg-surface-canvas px-3 text-body text-fg-primary hover:border-line-strong";

export function MachineCrossLinks({
  machineId,
  canCaptureNote,
  canRequestPrediction,
  className,
}: MachineCrossLinksProps) {
  return (
    <nav aria-label="Schnellaktionen" className={cx("flex flex-wrap gap-2", className)}>
      {canCaptureNote ? (
        <Link href={`/capture?machine=${machineId}`} className={LINK_CLASS}>
          Notiz erfassen
        </Link>
      ) : null}
      {canRequestPrediction ? (
        <Link href={`/insights/prediction?machine=${machineId}`} className={LINK_CLASS}>
          Vorhersage anfordern
        </Link>
      ) : null}
      <Link href={`/insights?machine=${machineId}`} className={LINK_CLASS}>
        Ereigniskette
      </Link>
    </nav>
  );
}
