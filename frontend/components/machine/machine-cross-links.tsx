// ============================================================
//  FOREMAN Frontend — components/machine/machine-cross-links.tsx
//  Zweck: Schnellaktionen der Maschinen-Detail-Sicht — nie Anlagen-Schaltung
//         (HITL, §4B). Notiz erfassen führt weiterhin zu J (/capture); Vorhersage
//         und Ereigniskette öffnen seit dem 02.09.2026 AN ORT UND STELLE.
//  Warum der Unterschied (und er ist keine Geschmacksfrage): Wer eine Maschine
//         ansieht und eine Einschätzung dazu will, verliert beim Wegspringen den
//         Zusammenhang — Sensorverlauf, offene Alarme und Stammdaten stehen dann
//         nicht mehr daneben, und der Rückweg kostet einen Klick und die
//         Scrollposition. Die Notiz-Erfassung ist der Gegenfall: Sie ist ein
//         eigenes Formular mit eigenem Absenden, und dorthin gehört ein Wechsel.
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3, client).
// ============================================================
import Link from "next/link";

import { cx } from "@/lib/ui/cx";

/** Welche eingebettete Sicht gerade offen ist. `null` = keine. */
export type MachineEinblendung = "vorhersage" | "ketten" | null;

export interface MachineCrossLinksProps {
  machineId: number;
  /** Werker/Schichtleiter/Techniker dürfen Notizen erfassen (→ J). */
  canCaptureNote: boolean;
  /** Nur Schichtleiter/Manager fordert eine Vorhersage an (On-Demand). */
  canRequestPrediction: boolean;
  /** Die offene Einblendung — trägt `aria-expanded` und die Beschriftung. */
  offen: MachineEinblendung;
  onToggle: (was: Exclude<MachineEinblendung, null>) => void;
  /** Kennungen der eingeblendeten Bereiche, für `aria-controls`. */
  vorhersageId: string;
  kettenId: string;
  className?: string;
}

const AKTION_CLASS =
  "touch-target inline-flex items-center rounded-md border border-line-subtle bg-surface-canvas px-3 text-body text-fg-primary hover:border-line-strong";

/** Gedrückter Schalter bleibt sichtbar gedrückt — nicht nur über `aria-pressed`. */
const OFFEN_CLASS = "border-line-strong bg-surface-overlay";

export function MachineCrossLinks({
  machineId,
  canCaptureNote,
  canRequestPrediction,
  offen,
  onToggle,
  vorhersageId,
  kettenId,
  className,
}: MachineCrossLinksProps) {
  return (
    <nav aria-label="Schnellaktionen" className={cx("flex flex-wrap gap-2", className)}>
      {canCaptureNote ? (
        <Link href={`/capture?machine=${machineId}`} className={AKTION_CLASS}>
          Notiz erfassen
        </Link>
      ) : null}
      {canRequestPrediction ? (
        <button
          type="button"
          aria-expanded={offen === "vorhersage"}
          aria-controls={vorhersageId}
          onClick={() => onToggle("vorhersage")}
          className={cx(AKTION_CLASS, offen === "vorhersage" && OFFEN_CLASS)}
        >
          {/* NICHT "Vorhersage anfordern": So heisst der Auslöser INNERHALB des
              eingeblendeten Bereichs. Zwei gleichnamige Knöpfe mit verschiedener
              Bedeutung sind für eine Vorlesehilfe nicht zu trennen — und für
              einen Menschen auch nicht. Dieser hier blendet ein; angefordert
              wird drinnen. */}
          {offen === "vorhersage" ? "Vorhersage ausblenden" : "Vorhersage"}
        </button>
      ) : null}
      <button
        type="button"
        aria-expanded={offen === "ketten"}
        aria-controls={kettenId}
        onClick={() => onToggle("ketten")}
        className={cx(AKTION_CLASS, offen === "ketten" && OFFEN_CLASS)}
      >
        {offen === "ketten" ? "Ereignisketten ausblenden" : "Ereigniskette"}
      </button>
    </nav>
  );
}
