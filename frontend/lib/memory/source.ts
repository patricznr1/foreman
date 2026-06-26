// ============================================================
//  FOREMAN Frontend — lib/memory/source.ts
//  Zweck: Quelltyp eines Archiv-Treffers MEHRKANALIG (Studie §4H formcodiert, §5.8):
//         Form/Kuerzel + deutsches Label, NICHT nur Farbe. Drei Quellen: Schichtnotiz
//         / Wartung / Alarm. Reine Hallensprache (kein Verfahrensbegriff).
//  Architektur-Einordnung: Darstellungs-Wording (Schicht 1/2). Reine Daten.
// ============================================================
import type { SourceType } from "./types";

/** Deutsches Hallensprache-Label je Quelltyp. */
export const SOURCE_LABEL: Record<SourceType, string> = {
  note: "Schichtnotiz",
  maintenance: "Wartung",
  alarm: "Alarm",
};

/** Farbunabhaengiges Form-Kuerzel je Quelltyp (zweiter Kanal). */
export const SOURCE_GLYPH: Record<SourceType, string> = {
  note: "N",
  maintenance: "W",
  alarm: "A",
};
