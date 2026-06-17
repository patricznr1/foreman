// ============================================================
//  FOREMAN Frontend — lib/memory/types.ts
//  Zweck: Das abgeleitete View-Modell der Gedächtnis-Suche (Sektion H, Studie §4H).
//         Transport-agnostisch aus WorkerNoteRead zusammengeführt (view-model.ts).
//         Traegt NIE einen Verfahrensnamen (Paraphrase-Disziplin §0/§1.3) und NIE
//         eine Scheingenauigkeit: das Backend liefert KEINEN Score — die
//         REIHENFOLGE ist das Relevanz-Signal, hier als ordinale Stufe + Rang.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Daten.
// ============================================================

/**
 * Quelltyp eines Treffers. Heterogen angelegt (Studie §4H: Notiz/Ereignis/Kette/
 * Wartung), aber das Gedächtnis liefert derzeit AUSSCHLIESSLICH Schichtnotizen.
 * Weitere Typen sind reserviert und werden NICHT erfunden (graceful).
 */
export type SourceType = "note"; // reserviert: | "event" | "chain" | "maintenance"

/**
 * Relevanz als ORDINALE Naehe-Stufe, abgeleitet aus der Rang-Position. Bewusst
 * dreistufig und RELATIV zur jeweiligen Suche — niemals ein Prozentwert
 * (das Backend liefert keinen Score; jede Prozentzahl waere Scheingenauigkeit).
 */
export type RelevanceStrength = "stark" | "mittel" | "entfernt";

/**
 * Beziehungstyp zwischen Treffern (Studie §4H Verknuepfungslogik). Aktiv sind NUR
 * die aus realen Feldern ableitbaren Typen; die klassen-/wurzelursachen-basierte
 * Verknuepfung ist reserviert (das Gedaechtnis liefert weder Klasse noch Aufloesung).
 */
export type RelationType = "same_machine" | "same_shift" | "temporal";

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
   * Aufloesungs-/Klassifikationsfeld. Reserviert, graceful null (nicht erfunden).
   */
  resolution: string | null;
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
