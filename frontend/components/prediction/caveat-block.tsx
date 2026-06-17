// ============================================================
//  FOREMAN Frontend — components/prediction/caveat-block.tsx
//  Zweck: Block 4 (Vorbehalt, Studie §4E/§5.2) — gleichwertig und im selben Rahmen
//         wie die Konfidenz, NIE wegklappbar, NIE unter „mehr". Feste, ruhige
//         Signalfarbe note/caveat (KEIN Alarm-Rot) mit konstantem Symbol. Text
//         DETERMINISTISCH vom Backend (validation_caveat), nie hier formuliert.
//         Defensive zweite Linie zum Negativ-Guard: ein leerer Vorbehalt erscheint
//         nie als Karte, sondern als Fehlerhinweis.
//  Architektur-Einordnung: Block-Komponente (Schicht 2). Rein präsentational.
// ============================================================
import { dataRegimeLabel, validationStatusLabel } from "@/lib/prediction/caveat";
import type { CaveatModel } from "@/lib/prediction/types";

/** Konstantes Vorbehalt-Symbol (Info-Kreis) — kein Alarm-Dreieck (es ist kein Alarm). */
function CaveatIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className="h-5 w-5 shrink-0 fill-none stroke-note-caveat"
      strokeWidth={1.6}
    >
      <circle cx="10" cy="10" r="8" />
      <line x1="10" y1="9" x2="10" y2="14" strokeLinecap="round" />
      <circle cx="10" cy="6.2" r="0.4" className="fill-note-caveat stroke-note-caveat" />
    </svg>
  );
}

export function CaveatBlock({ caveat }: { caveat: CaveatModel }) {
  // Defensive zweite Linie (der view-model-Guard verhindert das bereits): ein
  // leerer Vorbehalt darf nie als Karte erscheinen.
  if (!caveat.text || caveat.text.trim().length === 0) {
    return (
      <section
        data-block="caveat"
        role="alert"
        className="flex items-center gap-3 rounded-lg border border-note-caveat/50 bg-note-caveat/10 p-4 text-note-caveat"
      >
        <CaveatIcon />
        <p className="text-body">Vorbehalt fehlt — Erkenntnis nicht anzeigbar (Datenfehler).</p>
      </section>
    );
  }

  return (
    <section
      data-block="caveat"
      role="note"
      aria-label="Vorbehalt"
      className="flex gap-3 rounded-lg border border-note-caveat/50 bg-note-caveat/10 p-4"
    >
      <CaveatIcon />
      <div className="flex flex-col gap-2">
        <h3 className="text-caption font-semibold uppercase tracking-wide text-note-caveat">
          Vorbehalt
        </h3>
        <p className="text-body text-fg-secondary">{caveat.text}</p>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-caption text-fg-muted">
          <div className="flex gap-1">
            <dt>Datenbasis:</dt>
            <dd className="text-fg-secondary">{dataRegimeLabel(caveat.dataRegime)}</dd>
          </div>
          <div className="flex gap-1">
            <dt>Validierung:</dt>
            <dd className="text-fg-secondary">{validationStatusLabel(caveat.validationStatus)}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
