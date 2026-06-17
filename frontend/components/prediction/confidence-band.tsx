// ============================================================
//  FOREMAN Frontend — components/prediction/confidence-band.tsx
//  Zweck: Block 1 (Konfidenz, Studie §4E/§5.2). Eine ruhige Farbe, sichtbare
//         Bandbreite, KEINE Ampel-Dramatik, KEINE Scheingenauigkeit: die grobe
//         verbale Stufe ist der Anker, das Band zeigt einen gerundeten Bereich
//         (kein „87,3 %") über dem Vorlauf-Horizont. Der Schwellwert ist markiert.
//         Das Band ist dekorativ (aria-hidden); Stufe, Vorlauf und gerundeter
//         Bereich stehen als echter Text (farbunabhängig, screenreader-lesbar).
//  Architektur-Einordnung: Block-Komponente (Schicht 2). Rein präsentational.
// ============================================================
import { CONFIDENCE_LEVEL_LABEL } from "@/lib/prediction/confidence";
import type { ConfidenceModel } from "@/lib/prediction/types";

/** Vorlauf-Horizont in Hallensprache (volle Tage, sonst Stunden). */
function formatHorizon(hours: number): string {
  if (hours > 0 && hours % 24 === 0) {
    const days = hours / 24;
    return `${days} ${days === 1 ? "Tag" : "Tage"}`;
  }
  return `${hours} ${hours === 1 ? "Stunde" : "Stunden"}`;
}

export function ConfidenceBand({
  confidence,
  horizonH,
}: {
  confidence: ConfidenceModel;
  horizonH: number;
}) {
  const lowPct = Math.round(confidence.bandLow * 100);
  const highPct = Math.round(confidence.bandHigh * 100);
  const thresholdPct = Math.round(confidence.threshold * 100);
  const levelLabel = CONFIDENCE_LEVEL_LABEL[confidence.level];

  return (
    <section data-block="confidence" aria-label="Konfidenz" className="flex flex-col gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-h2 font-semibold text-fg-primary">{levelLabel}</span>
        <span className="text-caption text-fg-muted">Vorlauf: {formatHorizon(horizonH)}</span>
      </div>
      {/* Band: eine ruhige Farbe, sichtbare Breite; Schwellwert als Markierungslinie.
          Dekorativ — die Aussage steht als Text darüber/darunter (farbunabhängig). */}
      <div aria-hidden="true" className="relative h-3 w-full rounded-full bg-surface-overlay">
        <div
          className="absolute inset-y-0 rounded-full bg-data-series-1"
          style={{ left: `${lowPct}%`, width: `${Math.max(highPct - lowPct, 2)}%` }}
        />
        <div
          className="absolute inset-y-[-3px] w-0.5 bg-fg-secondary"
          style={{ left: `${thresholdPct}%` }}
        />
      </div>
      <p className="text-caption text-fg-muted">
        Grobe Einschätzung: ca. {lowPct}–{highPct} % — keine Nachkommastellen. Schwelle bei{" "}
        {thresholdPct} %.
      </p>
    </section>
  );
}
