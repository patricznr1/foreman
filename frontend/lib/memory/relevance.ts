// ============================================================
//  FOREMAN Frontend — lib/memory/relevance.ts
//  Zweck: Relevanz als STÄRKE/POSITION ableiten (Studie §4H: dezente Stufung,
//         kein lauter Score). Das Backend liefert KEINEN Ähnlichkeitswert — die
//         Reihenfolge ist das einzige ehrliche Signal. Daraus eine grobe,
//         ordinale Nähe-Stufe (relativ zur Suche), NIEMALS ein Prozentwert.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Funktion.
// ============================================================
import type { RelevanceStrength } from "./types";

/**
 * Ordinale Nähe-Stufe aus der Rang-Position. Drittelung der Liste: oberes Drittel
 * stark, mittleres mittel, unteres entfernt. Bei einem einzigen Treffer: stark
 * (er ist der ähnlichste). Das ist eine RELATIVE Aussage über die Reihenfolge
 * dieser Suche, keine absolute Ähnlichkeit.
 */
export function strengthFromRank(rank: number, total: number): RelevanceStrength {
  if (total <= 1) {
    return "stark";
  }
  const fraction = rank / (total - 1); // 0 (oben) bis 1 (unten)
  if (fraction <= 1 / 3) {
    return "stark";
  }
  if (fraction <= 2 / 3) {
    return "mittel";
  }
  return "entfernt";
}

/** Anzeige-Label der Nähe-Stufe (Hallensprache, kein Verfahrensname). */
export const STRENGTH_LABEL: Record<RelevanceStrength, string> = {
  stark: "starke Nähe",
  mittel: "mittlere Nähe",
  entfernt: "entferntere Nähe",
};

/** Farbunabhängige Stärke als Pip-Anzahl (zweiter Kanal, 1 bis 3). */
export const STRENGTH_PIPS: Record<RelevanceStrength, number> = {
  stark: 3,
  mittel: 2,
  entfernt: 1,
};
