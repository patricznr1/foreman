// ============================================================
//  FOREMAN Frontend — components/event-chains/chain-symbol.tsx
//  Zweck: Bespoke, token-getriebenes SVG-Symbol je Kettenereignis (Studie §4D/§5.8):
//         die FORM trägt die Bedeutung (mehrkanalig, nicht Farbe). KEINE Charting-/
//         Icon-Lib. Alarm = gefülltes Dreieck, Abweichung = offenes Dreieck
//         (abgesetzt), Notiz = Stift, Wartung = Schraube/Sechskant, Anker = Dreieck
//         im Ring (hervorgehoben). Entsättigt (`currentColor`) — KEINE Severity-Farbe
//         (die lebt nur am verlinkten Original-Alarm in C).
//  Architektur-Einordnung: bespoke SVG-Atom (Schicht 2).
// ============================================================
import { cx } from "@/lib/ui/cx";
import type { ChainSymbolKind } from "@/lib/event-chains/types";

export interface ChainSymbolProps {
  kind: ChainSymbolKind;
  className?: string;
}

/** Reiner SVG-Körper je Symbolklasse (24×24, `currentColor`). */
function shape(kind: ChainSymbolKind) {
  switch (kind) {
    case "anchor":
      // Hervorgehoben: gefülltes Dreieck im Ring.
      return (
        <>
          <circle cx="12" cy="12" r="11" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M12 6 L18 17 L6 17 Z" fill="currentColor" />
        </>
      );
    case "alarm":
      // Alarm: gefülltes Dreieck (Form-Konsistenz mit B).
      return <path d="M12 3 L21 20 L3 20 Z" fill="currentColor" />;
    case "drift":
      // Abweichung: OFFENES Dreieck — visuell abgesetzt vom gefüllten Alarm.
      return (
        <path
          d="M12 4 L20 19 L4 19 Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
        />
      );
    case "note":
      // Notiz: Stift (Diagonale + Spitze).
      return (
        <path
          d="M5 21 L4 17 L15 6 L18 9 L7 20 Z M14 7 L17 10"
          fill="currentColor"
          stroke="currentColor"
          strokeWidth="0.5"
          strokeLinejoin="round"
        />
      );
    case "maintenance":
      // Wartung: Sechskant-Schraube mit Bohrung.
      return (
        <>
          <polygon
            points="12,3 19,7.5 19,16.5 12,21 5,16.5 5,7.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          <circle cx="12" cy="12" r="3" fill="currentColor" />
        </>
      );
  }
}

export function ChainSymbol({ kind, className }: ChainSymbolProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      className={cx("h-5 w-5 shrink-0", className)}
      data-symbol={kind}
    >
      {shape(kind)}
    </svg>
  );
}
