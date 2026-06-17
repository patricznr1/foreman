// ============================================================
//  FOREMAN Frontend — components/memory/source-glyph.tsx
//  Zweck: Quelltyp eines Treffers MEHRKANALIG (Studie §4H "formcodiert", §5.8):
//         Form-Kürzel im Rahmen-Badge + deutsches Label, NICHT nur Farbe. Neutral
//         gehalten (kein FCSM-Zustandston — ein Treffer ist kein Anlagenzustand).
//         Konsistente Form-Logik wie der StatusIndicator (Buchstaben-Badge).
//  Architektur-Einordnung: Atom (Schicht 2). Rein präsentational.
// ============================================================
import { SOURCE_GLYPH, SOURCE_LABEL } from "@/lib/memory/source";
import type { SourceType } from "@/lib/memory/types";
import { cx } from "@/lib/ui/cx";

export interface SourceGlyphProps {
  source: SourceType;
  showLabel?: boolean;
  className?: string;
}

export function SourceGlyph({ source, showLabel = true, className }: SourceGlyphProps) {
  const label = SOURCE_LABEL[source];
  return (
    <span className={cx("inline-flex items-center gap-2", className)} role="img" aria-label={label}>
      <span
        aria-hidden="true"
        className="inline-flex h-7 min-w-7 items-center justify-center rounded-md border border-line-strong bg-surface-overlay px-1.5 font-mono text-caption font-semibold text-fg-secondary"
      >
        {SOURCE_GLYPH[source]}
      </span>
      {showLabel ? <span className="text-caption text-fg-secondary">{label}</span> : null}
    </span>
  );
}
