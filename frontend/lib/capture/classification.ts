// ============================================================
//  FOREMAN Frontend — lib/capture/classification.ts
//  Zweck: Die drei Werker-Kategorien als geordnete, mehrkanalig kodierbare
//         Definition (Studie §4J/§5.8: Bedeutung über Farbe + Form/Glyph + Label,
//         nie Farbe allein). Reine Daten/Logik — die konkrete Farb-Zuordnung
//         (Token-Klassen) liegt purge-sicher in der Komponente (CategoryButtons).
//         Der Werker wählt die Kategorie MANUELL; ein automatischer Vorschlag ist
//         [VISION] und wird bewusst NICHT erfunden.
//  Architektur-Einordnung: Erfassungs-Logik (Schicht 2). Reine Logik, testbar.
// ============================================================
import type { Classification } from "./types";

export interface ClassificationOption {
  id: Classification;
  /** Deutsches UI-Label (Hallensprache, kurz). */
  label: string;
  /** Kurzer Sinn-Hinweis (a11y-Beschreibung / Titel). */
  hint: string;
  /** Form-Glyph als ZWEITER Kanal neben der Farbe (zunehmende Füllung = Dringlichkeit). */
  glyph: string;
  /** Ordinaler Dringlichkeitsrang (routine < auffaellig < kritisch). */
  rank: number;
}

/** Geordnet von ruhig nach dringend — die Reihenfolge ist die Anzeige-Reihenfolge. */
export const CLASSIFICATIONS: readonly ClassificationOption[] = [
  { id: "routine", label: "Routine", hint: "Routinebeobachtung, nichts Auffälliges", glyph: "○", rank: 0 },
  { id: "auffaellig", label: "Auffällig", hint: "Auffälligkeit, im Blick behalten", glyph: "◐", rank: 1 },
  { id: "kritisch", label: "Kritisch", hint: "Kritisch, dringend ansehen", glyph: "●", rank: 2 },
];

/** Holt die Definition zu einer Kategorie (jede Classification ist abgedeckt). */
export function classificationOption(id: Classification): ClassificationOption {
  const found = CLASSIFICATIONS.find((option) => option.id === id);
  if (!found) {
    // Defensiv — ein Test sichert die Vollständigkeit der Tabelle.
    throw new Error(`Unbekannte Kategorie: ${id}`);
  }
  return found;
}

/** Type-Guard für Werte aus URL/Storage (verwirft Fremdwerte still). */
export function isClassification(value: string | null | undefined): value is Classification {
  return value === "routine" || value === "auffaellig" || value === "kritisch";
}
