// ============================================================
//  FOREMAN Frontend — lib/memory/gruppen.ts
//  Zweck: Teilt das FUSIONIERTE Archiv-Ergebnis in Bloecke je Quelle auf —
//         Aggregated Search im Sinne von Lalmas (vertical selection / item
//         selection / result presentation), aber ohne zweite Abfrage.
//  Architektur-Einordnung: View-State (Schicht 1). Reine Funktion, testbar.
//
//  WARUM AUS DEM ERGEBNIS UND NICHT AUS VIER ABFRAGEN — das ist die tragende
//  Entscheidung dieser Datei: Seit die Fusion auf den Vorgang zusammenfuehrt,
//  kann eine Wartung ueber das GEDAECHTNIS in die Liste kommen und dort als
//  `maintenance` stehen. Eine Nachfrage mit `sources=maintenance` liefe gegen
//  den reinen Volltext und faende sie NICHT (gemessen: ein Volltext-Treffer
//  ueber zehn Anfragen, C-081). Der Block widerspraeche dem Ranking direkt
//  darueber — und der Werker haette zwei Antworten auf dieselbe Frage.
//
//  Der zweite Grund ist billiger, aber auch gut: keine vier zusaetzlichen
//  Abfragen je Suche.
// ============================================================
import { VERFUEGBARE_QUELLEN } from "./source";
import type { ArchiveHitView, SourceType } from "./types";

/** Ein Block: eine Quelle und die Treffer, die sie beigesteuert hat. */
export interface QuellenGruppe {
  source: SourceType;
  /** In der Reihenfolge des Rangs — die Gruppierung sortiert nicht um. */
  hits: ArchiveHitView[];
}

/**
 * Gruppiert die Treffer nach dem Quelltyp, den sie TRAGEN.
 *
 * Sortiert wird NICHT: Innerhalb eines Blocks bleibt die Reihenfolge des
 * globalen Rangs erhalten. Eine zweite Sortierung waere eine zweite Aussage
 * darueber, was relevanter ist — und die Fusion hat sie schon getroffen.
 *
 * LEERE QUELLEN FALLEN WEG. Ein Block „Alarm — 0 Treffer" bei jeder Suche ist
 * kein Hinweis, sondern Rauschen; welche Quellen ueberhaupt befragt wurden,
 * sagt der Herkunfts-Stempel der Ergebnisliste. Die feste Reihenfolge aus
 * `VERFUEGBARE_QUELLEN` bleibt: Die Bloecke sollen zwischen zwei Suchen nicht
 * springen.
 *
 * `source` und nicht `foundBy`: Ein Treffer, den Notiz UND Gedaechtnis gefunden
 * haben, gehoert in den Notiz-Block — er IST eine Notiz. Dass das Gedaechtnis
 * ihn bestaetigt hat, steht auf der Karte („Auch im Gedaechtnis"), nicht in der
 * Einteilung. Ihn in beide Bloecke zu legen hiesse, denselben Vorgang zweimal
 * zu zeigen, und genau das hat die Fusion gerade abgeschafft.
 */
export function gruppiereNachQuelle(hits: ArchiveHitView[]): QuellenGruppe[] {
  return VERFUEGBARE_QUELLEN.map((source) => ({
    source,
    hits: hits.filter((hit) => hit.source === source),
  })).filter((gruppe) => gruppe.hits.length > 0);
}

/**
 * Wie viele Treffer eine zweite Quelle unabhaengig bestaetigt hat.
 *
 * Das ist die Zahl, die es vor dem 27.08.2026 nicht geben konnte: Damals wurde
 * ein Treffer, den zwei Quellen fanden, entdoppelt — die Einigkeit verschwand
 * genau dann, wenn sie entstand. Jetzt hebt sie den Treffer, und die Anzeige
 * kann sagen, wie oft das vorkam.
 */
export function anzahlBestaetigt(hits: ArchiveHitView[]): number {
  return hits.filter((hit) => hit.foundBy.length > 1).length;
}
