// ============================================================
//  FOREMAN Frontend — lib/memory/view-model.ts
//  Zweck: Führt die rohe F-SEM-Antwort (list[WorkerNoteRead], nach Nähe sortiert,
//         OHNE Score) in das anzeigbare MemorySearchResult über (Studie §4H).
//         Bewahrt die Backend-Reihenfolge als Rang (= Relevanz-Signal), maskiert
//         den Autor (#hex6, §8), kürzt den bereits maskierten Text zum Auszug und
//         leitet Verdichtung + Verknüpfung ab. Erfindet nichts: Auflösung bleibt
//         null, solange das Gedächtnis kein Auflösungsfeld führt.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Funktion, testbar.
// ============================================================
import type { ArchiveHit, WorkerNoteRead } from "@/lib/api/contracts";
import { maskPseudonym } from "@/lib/ui/pii";
import { clusterByMachine } from "./cluster";
import { deriveRelations } from "./relations";
import { strengthFromRank } from "./relevance";
import { toExcerpt } from "./excerpt";
import type {
  ArchiveSearchResult,
  MemoryHit,
  MemorySearchResult,
  SourceType,
} from "./types";

/** Baut das vollständige, sortierte Suchergebnis aus der F-SEM-Antwort. */
export function assembleSearchResult(notes: WorkerNoteRead[], query: string): MemorySearchResult {
  const total = notes.length;
  const hits: MemoryHit[] = notes.map((note, index) => ({
    id: note.id,
    source: "note",
    machineId: note.machine_id,
    shift: note.shift,
    excerpt: toExcerpt(note.text),
    text: note.text,
    authorHandle: maskPseudonym(note.author),
    createdAt: note.created_at,
    rank: index,
    strength: strengthFromRank(index, total),
    // Das Gedächtnis führt kein Auflösungsfeld — graceful null.
    resolution: null,
    // Eine Schichtnotiz ist keiner Anlagenkomponente zugeordnet; das Bauteil
    // kommt über Alarm und Wartung. Immer gesetzt, damit „nicht erhoben" und
    // „nicht vorhanden" nicht gleich aussehen.
    componentType: null,
    componentLabel: null,
  }));

  return {
    query,
    hits,
    clusters: clusterByMachine(hits),
    relations: deriveRelations(hits),
    total,
  };
}

/**
 * Baut das flache Archiv-Ergebnis (Paket 1c) aus der quellenuebergreifenden Antwort.
 * Bewusst SCHLICHT: Reihenfolge=Rang, keine Verdichtung/Verknuepfung, kein Score,
 * kein Autor. Der Auszug kommt backend-seitig bereits gekuerzt (kein erneutes Kuerzen).
 */
export function assembleArchiveResult(
  hits: ArchiveHit[],
  query: string,
  sources: SourceType[],
): ArchiveSearchResult {
  return {
    query,
    sources,
    hits: hits.map((hit, index) => ({
      source: hit.source_type,
      id: hit.id,
      machineId: hit.machine_id,
      timestamp: hit.timestamp,
      excerpt: hit.excerpt,
      detail: hit.detail,
      rank: index,
      // Faellt das Feld weg (aeltere Backend-Fassung) oder kommt es leer, steht
      // die eigene Quelle allein da. Eine leere Liste waere schlimmer als eine
      // fehlende Auskunft: Die Anzeige laese sie als "niemand hat das gefunden".
      foundBy: hit.gefunden_von?.length ? hit.gefunden_von : [hit.source_type],
    })),
    total: hits.length,
  };
}
