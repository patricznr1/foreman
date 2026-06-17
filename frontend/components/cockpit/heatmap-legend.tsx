// ============================================================
//  FOREMAN Frontend — components/cockpit/heatmap-legend.tsx
//  Zweck: Lese-Legende der DriftHeatmap (§4A/§5.2). Erklärt die zwei Kanäle der
//         Zelle in Hallensprache: die entsättigte sequenzielle Intensität (niedrig→
//         hoch) und die farbunabhängige Schraffur (Abweichung vs. offene Warnung).
//         Token-getrieben (var(--color-*)); die Schraffur-Muster sind hier rein
//         dekorativ als CSS-Verlauf (die Zellen selbst nutzen das SVG-Pattern).
//  Architektur-Einordnung: Darstellung (Schicht 3). Rein präsentational.
// ============================================================
const INTENSITY_LEVELS = [1, 2, 3, 4, 5] as const;

const HATCH_OVER = "repeating-linear-gradient(45deg, var(--color-diff-over) 0 1.4px, transparent 1.4px 6px)";
const HATCH_UNDER = "repeating-linear-gradient(-45deg, var(--color-diff-under) 0 1.4px, transparent 1.4px 6px)";

export function HeatmapLegend() {
  return (
    <figure className="flex flex-col gap-2" aria-label="Legende der Heatmap">
      <figcaption className="text-caption text-fg-muted">Abweichung</figcaption>
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-caption text-fg-muted">niedrig</span>
          <span className="flex" aria-hidden="true">
            {INTENSITY_LEVELS.map((level) => (
              <span
                key={level}
                className="h-4 w-5 first:rounded-l-sm last:rounded-r-sm"
                style={{ backgroundColor: `var(--color-heatmap-${level})` }}
              />
            ))}
          </span>
          <span className="text-caption text-fg-muted">hoch</span>
        </div>

        <div className="flex items-center gap-2">
          <span
            className="h-4 w-5 rounded-sm border border-line-subtle"
            style={{ backgroundColor: "var(--color-surface-raised)", backgroundImage: HATCH_OVER }}
            aria-hidden="true"
          />
          <span className="text-caption text-fg-secondary">Abweichung erkannt</span>
        </div>

        <div className="flex items-center gap-2">
          <span
            className="h-4 w-5 rounded-sm border border-line-subtle"
            style={{ backgroundColor: "var(--color-surface-raised)", backgroundImage: HATCH_UNDER }}
            aria-hidden="true"
          />
          <span className="text-caption text-fg-secondary">Offene Warnung</span>
        </div>
      </div>
    </figure>
  );
}
