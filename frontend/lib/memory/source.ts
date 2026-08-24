// ============================================================
//  FOREMAN Frontend — lib/memory/source.ts
//  Zweck: Quelltyp eines Archiv-Treffers MEHRKANALIG (Studie §4H formcodiert, §5.8):
//         Form/Kuerzel + deutsches Label, NICHT nur Farbe. Vier Quellen: Schichtnotiz
//         / Wartung / Alarm / Gedaechtnis (§15.10). Reine Hallensprache (kein
//         Verfahrensbegriff).
//  Architektur-Einordnung: Darstellungs-Wording (Schicht 1/2). Reine Daten.
// ============================================================
import type { ArchiveHitView, SourceType } from "./types";

/** Deutsches Hallensprache-Label je Quelltyp. */
export const SOURCE_LABEL: Record<SourceType, string> = {
  note: "Schichtnotiz",
  maintenance: "Wartung",
  alarm: "Alarm",
  // Hallensprache, kein Verfahrensbegriff: der Werker liest, woher der Treffer
  // kommt, nicht wie er zustande kam.
  memory: "Aus dem Gedächtnis",
};

/**
 * Die Quellen, die die Anzeige heute ANBIETET und ANFRAGT — EINE Quelle der
 * Wahrheit fuer Umschalter und Suchaufruf.
 *
 * WARUM "memory" HIER FEHLT: Die vierte Quelle ist gebaut (§15.10), das
 * Backend nimmt sie an, und Label, Kuerzel und Detail-Anzeige tragen sie
 * bereits. Sie steht aber hinter einem Backend-Schalter, der per Default AUS
 * ist. Wuerde die Anzeige sie trotzdem anfragen, behauptete der
 * Herkunfts-Stempel eine Quelle, die nie befragt wurde — eine falsche Aussage
 * ueber die eigene Datenlage, genau das, was §15.10 mit "keine Tarnung"
 * ausschliesst.
 *
 * BEIDE SCHALTER GEHOEREN GEMEINSAM UMGELEGT: hier "memory" ergaenzen UND
 * FOREMAN_ARCHIVE_SUBSTRATE_ENABLED setzen. Vorbedingung ist das Goldset
 * (Freigabe-Bedingung 1). Diese Konstante ist die EINZIGE Stelle, die es
 * braucht — vorher lagen vier Listen verstreut, und eine vergessene waere ein
 * stiller Fehler gewesen.
 */
export const VERFUEGBARE_QUELLEN: readonly SourceType[] = ["note", "maintenance", "alarm"];

/** Farbunabhaengiges Form-Kuerzel je Quelltyp (zweiter Kanal). */
export const SOURCE_GLYPH: Record<SourceType, string> = {
  note: "N",
  maintenance: "W",
  alarm: "A",
  memory: "G",
};

/**
 * Eindeutiger Listen-Schluessel eines Treffers.
 *
 * WARUM NICHT NUR Quelle+id: Eine Erinnerung hat keinen Primaerschluessel und
 * traegt deshalb `id = 0` (Backend, bewusst — eine erfundene Zahl zeigte auf
 * eine fremde Zeile). Alle Erinnerungstreffer einer Liste haetten damit
 * denselben Schluessel; React wuerde sie beim Nachladen durcheinanderbringen
 * oder Zustand am falschen Element halten.
 *
 * Der Rang traegt die Eindeutigkeit: Er ist die Position im Ergebnis und
 * innerhalb einer Trefferliste per Konstruktion einmalig.
 */
export function hitKey(hit: ArchiveHitView): string {
  return `${hit.source}-${hit.id}-${hit.rank}`;
}
