// ============================================================
//  FOREMAN Frontend — lib/memory/testing/fixtures.ts
//  Zweck: Test-Fixtures für die Gedächtnis-Suche. makeNote() baut ein
//         WorkerNoteRead gegen den REALEN Vertrag (schemas/resources.py); der
//         Text ist bereits maskiert (wie vom Backend), der Autor ein HMAC-Token.
//  Architektur-Einordnung: Test-Hilfe (nur Tests).
// ============================================================
import type { ArchiveHit, WorkerNoteRead } from "@/lib/api/contracts";

let seq = 0;
let archiveSeq = 0;

/** Ein WorkerNoteRead mit sinnvollen Defaults; overrides überschreiben gezielt.
 *  (Für die eingefrorenen, assoziativen Tests — Verdichtung/Verknüpfung, Paket 3.) */
export function makeNote(overrides: Partial<WorkerNoteRead> = {}): WorkerNoteRead {
  seq += 1;
  return {
    id: seq,
    machine_id: 12,
    shift: "Frühschicht",
    text: "Lager läuft heiß nach Schichtwechsel, Geräusch an der Spindel.",
    classification: null,
    author: "v1:a3f9d8e2c1b40000000000000000000000000000000000000000000000000000",
    created_at: "2026-06-10T08:00:00+00:00",
    ...overrides,
  };
}

/** Ein ArchiveHit (Paket 1c) gegen den REALEN Vertrag (archive/schemas.py); Default
 *  ist eine Notiz, `detail`/`source_type`-Override macht Wartung/Alarm. */
export function makeArchiveHit(overrides: Partial<ArchiveHit> = {}): ArchiveHit {
  archiveSeq += 1;
  return {
    source_type: "note",
    id: archiveSeq,
    machine_id: 12,
    timestamp: "2026-06-10T08:00:00+00:00",
    excerpt: "Lager läuft heiß nach Schichtwechsel, Geräusch an der Spindel.",
    detail: { shift: "Frühschicht" },
    ...overrides,
  };
}
