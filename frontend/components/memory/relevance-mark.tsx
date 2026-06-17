// ============================================================
//  FOREMAN Frontend — components/memory/relevance-mark.tsx
//  Zweck: Relevanz als STÄRKE/POSITION (Studie §4H: dezente Stufung, kein lauter
//         Score). MEHRKANALIG (§5.8): Pip-Anzahl (Form) + Wort-Label + Rang-Text —
//         nie nur Farbe. NIEMALS ein Prozentwert (das Backend liefert keinen Score;
//         die Reihenfolge ist das Signal, hier als "Rang X von N").
//  Architektur-Einordnung: Atom (Schicht 2). Rein präsentational.
// ============================================================
import { STRENGTH_LABEL, STRENGTH_PIPS } from "@/lib/memory/relevance";
import type { RelevanceStrength } from "@/lib/memory/types";
import { cx } from "@/lib/ui/cx";

export interface RelevanceMarkProps {
  strength: RelevanceStrength;
  rank: number;
  total: number;
  className?: string;
}

export function RelevanceMark({ strength, rank, total, className }: RelevanceMarkProps) {
  const pips = STRENGTH_PIPS[strength];
  const label = STRENGTH_LABEL[strength];
  const position = `Rang ${rank + 1} von ${total}`;
  // Zugänglicher Name trägt Wort + Position — Relevanz ist nie nur farbcodiert.
  const accessibleName = `${label}, ${position}`;
  return (
    <span className={cx("inline-flex items-center gap-2", className)} role="img" aria-label={accessibleName}>
      <span aria-hidden="true" className="inline-flex items-center gap-0.5">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className={cx(
              "inline-block h-2.5 w-2.5 rounded-full",
              index < pips ? "bg-fg-secondary" : "bg-line-subtle",
            )}
          />
        ))}
      </span>
      <span aria-hidden="true" className="text-caption text-fg-muted">
        {label} · {position}
      </span>
    </span>
  );
}
