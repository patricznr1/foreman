// ============================================================
//  FOREMAN Frontend — lib/memory/verknuepfung.ts
//  Zweck: Bruecke zwischen der ausgelieferten Archiv-Trefferform (ArchiveHitView)
//         und der VERKNUEPFUNGS-Logik (cluster.ts / relations.ts / relevance.ts),
//         die auf MemoryHit rechnet.
//  Warum eine Bruecke und keine zweite Fassung der Logik: Verdichtung und
//         Beziehungen sind seit Paket 1c gebaut und geprueft, sie lagen nur nicht
//         gerendert da. Sie nachzubauen erzeugte eine zweite Wahrheit, die mit der
//         ersten auseinanderlaeuft — und beide saehen plausibel aus.
//  DIE FALLE, gegen die `id` hier gebaut ist: Eine Erinnerung traegt keinen
//         Primaerschluessel und kommt mit `id = 0`. Ueber die Rohkennung fielen
//         ALLE Erinnerungen auf denselben Schluessel zusammen — die Verdichtung
//         zoege sie zu einer Gruppe, und React vergaebe denselben Key mehrfach.
//         Deshalb traegt `id` hier den RANG: innerhalb einer Trefferliste
//         eindeutig, stabil, und zugleich der Index in `hits` — darueber findet
//         `zurueck` den vollen Treffer fuer die Anzeige wieder.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Funktionen.
// ============================================================
import { strengthFromRank } from "./relevance";
import type { ArchiveHitView, MemoryHit } from "./types";

/** Leerer Text bleibt null — "nicht erhoben" ist nicht dasselbe wie "leer". */
function text(wert: unknown): string | null {
  return typeof wert === "string" && wert.trim() ? wert.trim() : null;
}

/**
 * Uebersetzt die ausgelieferten Treffer in die Form, auf der die
 * Verknuepfungs-Logik rechnet.
 *
 * `text` bekommt den Auszug: Das Archiv liefert keinen ungekuerzten Volltext, und
 * ihn hier zu erfinden waere schlimmer als ihn zu kuerzen. `authorHandle` bleibt
 * null — das Archiv fuehrt bewusst kein Autor-Merkmal (§8).
 */
export function alsGedaechtnisTreffer(hits: readonly ArchiveHitView[]): MemoryHit[] {
  const total = hits.length;
  return hits.map((hit) => ({
    id: hit.rank,
    source: hit.source,
    machineId: hit.machineId,
    shift: text(hit.detail.shift),
    excerpt: hit.excerpt,
    text: hit.excerpt,
    authorHandle: null,
    createdAt: hit.timestamp,
    rank: hit.rank,
    strength: strengthFromRank(hit.rank, total),
    resolution: null,
    componentType: text(hit.detail.bauteilart),
    componentLabel: text(hit.detail.bauteil),
  }));
}

/**
 * Findet zu den uebersetzten Treffern die vollen zurueck — ueber den Rang, der
 * zugleich der Index ist.
 *
 * Ein Rang ausserhalb der Liste faellt weg, statt `undefined` in die Anzeige zu
 * lassen: Die Verknuepfungs-Logik gibt zwar nur zurueck, was sie bekommen hat,
 * aber ein spaeterer Aufrufer koennte Treffer aus zwei Laeufen mischen — und dann
 * zeigte die Gruppe eine leere Karte statt zu fehlen.
 */
export function zurueck(
  treffer: readonly MemoryHit[],
  hits: readonly ArchiveHitView[],
): ArchiveHitView[] {
  return treffer.map((t) => hits[t.id]).filter((hit): hit is ArchiveHitView => hit !== undefined);
}
