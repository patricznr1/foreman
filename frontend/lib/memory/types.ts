// ============================================================
//  FOREMAN Frontend — lib/memory/types.ts
//  Zweck: Das abgeleitete View-Modell der Gedächtnis-Suche (Sektion H, Studie §4H).
//         Transport-agnostisch aus WorkerNoteRead zusammengeführt (view-model.ts).
//         Traegt NIE einen Verfahrensnamen (Paraphrase-Disziplin §0/§1.3) und NIE
//         eine Scheingenauigkeit: das Backend liefert KEINEN Score — die
//         REIHENFOLGE ist das Relevanz-Signal, hier als ordinale Stufe + Rang.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Daten.
// ============================================================
import type { ArchiveHitDetail } from "@/lib/api/contracts";

/**
 * Quelltyp eines Treffers. Das Archiv durchsucht drei EIGENE Quellen —
 * Schichtnotiz / Wartung / Alarm — und seit §15.10 optional eine vierte:
 * "memory", eine Erinnerung aus dem Gedächtnis. Sie ist bewusst kein eigener
 * Anzeige-Sonderfall, sondern eine Quelle neben den anderen; nur ihre Herkunft
 * bleibt kenntlich.
 */
export type SourceType = "note" | "maintenance" | "alarm" | "memory";

/**
 * Relevanz als ORDINALE Naehe-Stufe, abgeleitet aus der Rang-Position. Bewusst
 * dreistufig und RELATIV zur jeweiligen Suche — niemals ein Prozentwert
 * (das Backend liefert keinen Score; jede Prozentzahl waere Scheingenauigkeit).
 */
export type RelevanceStrength = "stark" | "mittel" | "entfernt";

/**
 * Beziehungstyp zwischen Treffern (Studie §4H Verknuepfungslogik). Aktiv sind NUR
 * die aus realen Feldern ableitbaren Typen.
 *
 * `same_component` kam am 02.09.2026 dazu. Der Satz "das Gedaechtnis liefert weder
 * Klasse noch Aufloesung" stand hier zu Recht, solange die Spiegelung das Bauteil
 * nicht mitschickte; seit dem 28.08.2026 tut sie es (`bauteilart`/`bauteil` im
 * Detail). Das ist die tragende Verknuepfung des Gedaechtnisses: Zwei Maschinen
 * verschiedener Bauart teilen ein Bauteil, und ein Versagensmuster gehoert dem
 * Bauteil. Ueber die Maschine allein ist dieser Zusammenhang NICHT zu finden.
 *
 * Weiter reserviert bleibt die wurzelursachen-basierte Verknuepfung — ein
 * Aufloesungsfeld gibt es nach wie vor nicht.
 */
export type RelationType = "same_machine" | "same_shift" | "temporal" | "same_component";

/** Ein einzelner Treffer der Bedeutungssuche. */
export interface MemoryHit {
  id: number;
  source: SourceType;
  machineId: number | null;
  shift: string | null;
  /** Lesbarer, gekuerzter Auszug — backend-seitig bereits PII-maskiert. */
  excerpt: string;
  /** Voller (bereits maskierter) Text fuer die Detailansicht. */
  text: string;
  /** Maskiertes Autor-Handle (#hex6) oder null — nie Klartext (§8). */
  authorHandle: string | null;
  createdAt: string; // ISO 8601
  /** Rang-Position in der Trefferliste (0 = aehnlichster). */
  rank: number;
  /** Ordinale Naehe-Stufe aus der Rang-Position (kein Prozent). */
  strength: RelevanceStrength;
  /**
   * Aufloesung (geloest durch …) — derzeit NIE bekannt: das Gedaechtnis fuehrt kein
   * Aufloesungsfeld. Reserviert, graceful null (nicht erfunden).
   */
  resolution: string | null;
  /**
   * Bauteil des Vorgangs, sofern die Quelle es fuehrt. IMMER gesetzt (ggf. null) —
   * ein mal vorhandenes, mal fehlendes Feld liesse "nicht erhoben" wie "nicht
   * vorhanden" aussehen und zwaenge jeden Leser zu einer Fallunterscheidung.
   */
  componentType: string | null;
  componentLabel: string | null;
}

/** Eine Beziehung zwischen mehreren Treffern (kompakt, kein Graph). */
export interface MemoryRelation {
  type: RelationType;
  /** IDs der verknuepften Treffer (>= 2). */
  hitIds: number[];
  /** Faktischer Begruendungssatz in Hallensprache — aus realen Feldern, nicht erfunden. */
  reason: string;
}

/** Eine Verdichtung mehrerer Treffer an derselben Maschine. */
export interface MemoryCluster {
  /** Gruppierungsschluessel (derzeit: Maschine). */
  machineId: number;
  hits: MemoryHit[];
  /**
   * Aufloesungs-Bezug der Gruppe (alle geloest durch …) — graceful null, solange
   * das Gedaechtnis keine Aufloesung fuehrt. Wird im UI sichtbar als folgt markiert.
   */
  sharedResolution: string | null;
}

/** Das vollstaendige, sortierte Ergebnis einer Bedeutungssuche. */
export interface MemorySearchResult {
  /** Die natuerlichsprachliche Anfrage (fuer Anzeige/Ansage). */
  query: string;
  /** Treffer in Backend-Reihenfolge (Rang = Index), nach Naehe sortiert. */
  hits: MemoryHit[];
  /** Verdichtung: Gruppen mit >= 2 Treffern an derselben Maschine. */
  clusters: MemoryCluster[];
  /** Beziehungen zwischen Treffern (kompakte Verknuepfung, kein Graph). */
  relations: MemoryRelation[];
  /** Gesamtzahl Treffer (fuer die Live-Region-Ansage). */
  total: number;
}

// --- Archiv (Paket 1c): flacher, quellenuebergreifender Treffer ---
// Bewusst SCHLICHT: nur Wortlaut-Auszug + Quelle + Zeit + Maschine + quellen-
// spezifische, PII-freie Anzeige-Details. KEIN Score, KEIN Autor (ArchiveHit ist
// PII-frei), KEINE Verdichtung/Verknuepfung (die bleibt fuer Paket 3 reserviert).

/** Ein einzelner Archiv-Treffer fuer die Anzeige (Spiegel von ArchiveHit). */
export interface ArchiveHitView {
  source: SourceType;
  id: number;
  machineId: number | null;
  /** Quellen-normalisierter Zeitstempel (ISO 8601). */
  timestamp: string;
  /** Wortlaut-Auszug (backend-seitig gekuerzt + PII-maskiert bei Notizen). */
  excerpt: string;
  /** Quellenspezifische Anzeige-Details (PII-frei, kein HMAC-Token). */
  detail: ArchiveHitDetail;
  /** Rang-Position in der Trefferliste (0 = relevantester). */
  rank: number;
  /**
   * Welche Quellen diesen Vorgang gefunden haben. Mehr als eine heisst:
   * bestaetigt statt nur gefunden — zwei Ranglisten sind sich einig. `source`
   * bleibt davon unberuehrt und sagt weiter, WAS der Treffer ist.
   *
   * Faellt eine aeltere Backend-Fassung das Feld weg, steht hier die eigene
   * Quelle allein — nie eine leere Liste, damit die Anzeige nicht zwischen
   * "keine Auskunft" und "niemand hat es gefunden" unterscheiden muss.
   */
  foundBy: SourceType[];
}

/** Das flache, sortierte Ergebnis einer Archiv-Suche (Reihenfolge = Relevanz-Rang). */
export interface ArchiveSearchResult {
  query: string;
  /** Die aktiv durchsuchten Quellen (fuer den ehrlichen Herkunfts-Stempel). */
  sources: SourceType[];
  hits: ArchiveHitView[];
  total: number;
}
