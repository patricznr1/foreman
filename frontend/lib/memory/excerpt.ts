// ============================================================
//  FOREMAN Frontend — lib/memory/excerpt.ts
//  Zweck: Aus dem (bereits NER-maskierten) Notiztext einen lesbaren, gekuerzten
//         Auszug machen (Studie §4H: Karte mit Auszug). Wortgrenzen-schonend,
//         Mehrfach-Whitespace zusammengezogen. Maskierungs-Marker wie [PERSON]
//         bleiben erhalten — der Auszug erfindet nichts und entmaskiert nichts.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Funktion.
// ============================================================

const DEFAULT_MAX = 180;

/** Kuerzt den maskierten Text auf einen Auszug an der Wortgrenze (+ Auslassung). */
export function toExcerpt(text: string, max: number = DEFAULT_MAX): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= max) {
    return normalized;
  }
  const cut = normalized.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  const base = lastSpace > max * 0.6 ? cut.slice(0, lastSpace) : cut;
  return `${base.trimEnd()} …`;
}
