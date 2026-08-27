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
 * Die Quellen, die die Anzeige ANBIETET und ANFRAGT — EINE Quelle der Wahrheit
 * fuer Umschalter und Suchaufruf.
 *
 * "memory" ist seit dem 27.08.2026 dabei. Vorbedingung waren die sieben
 * Freigabe-Bedingungen aus GROUND_TRUTH §15.10, allen voran das Goldset:
 * gemessen an 18 Anfragen mit Relevanzurteilen von drei unabhaengigen
 * Beurteilern geht kein zutreffender Treffer verloren, und auf 66,7 % der
 * Anfragen kommt einer hinzu (Register C-066, C-068).
 *
 * DIESER SCHALTER HAT EINE ZWEITE HAELFTE: FOREMAN_ARCHIVE_SUBSTRATE_ENABLED im
 * Backend. Steht sie AUS, reicht `archive/router.py` den Substrat-Klienten
 * nicht durch — die Anzeige fragte dann eine Quelle an, die nie befragt wurde,
 * und ihr Herkunfts-Stempel behauptete etwas Falsches ueber die eigene
 * Datenlage. Genau das schliesst §15.10 mit "keine Tarnung" aus.
 *
 * WER SIE WIEDER AUSSCHALTET, schaltet BEIDE aus, und in dieser Reihenfolge:
 * erst hier, dann im Backend. Beim Einschalten umgekehrt. Die kurze
 * Zwischenlage "Backend liefert, Anzeige fragt nicht" ist harmlos; die
 * umgekehrte ist es nicht.
 *
 * Diese Konstante ist die EINZIGE Stelle, die es braucht — vorher lagen vier
 * Listen verstreut, und eine vergessene waere ein stiller Fehler gewesen.
 */
export const VERFUEGBARE_QUELLEN: readonly SourceType[] = [
  "note",
  "maintenance",
  "alarm",
  "memory",
];

/**
 * Der sichtbare Beleg dafuer, dass sich zwei Quellen einig sind — oder `null`.
 *
 * WOZU: Seit dem 27.08.2026 fuehrt die Fusion denselben Vorgang aus mehreren
 * Ranglisten zusammen und HEBT ihn dadurch (Einigkeit zaehlt doppelt). Vorher
 * wurde die Erinnerung in genau diesem Fall weggeworfen. Ohne dieses Label
 * bliebe die Hebung unsichtbar: Der Treffer stuende weiter oben, und niemand
 * saehe, warum — waehrend der Werker gerade DAS wissen will ("das hatten wir
 * schon, und das Gedaechtnis kennt es auch").
 *
 * Der eigene Treffer vertritt den Vorgang immer (Backend), deshalb ist die
 * fremde Quelle praktisch immer das Gedaechtnis. Der allgemeine Zweig steht
 * trotzdem da — er behauptet nur nichts ueber eine Paarung, die es nicht gibt.
 */
export function bestaetigungsLabel(hit: ArchiveHitView): string | null {
  const fremde = hit.foundBy.filter((quelle) => quelle !== hit.source);
  if (fremde.length === 0) {
    return null;
  }
  return fremde.includes("memory") ? "Auch im Gedächtnis" : "Von mehreren Quellen bestätigt";
}

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
