// ============================================================
//  FOREMAN Frontend — lib/machine/history.ts
//  Zweck: Vereint Wartungs-/Prüfereignisse und Werker-Notizen zu EINER chronologischen
//         Maschinen-Historie (jüngste zuerst), transport-agnostisch. PII-Disziplin (§8):
//         Akteure (`performed_by`/`author`) sind HMAC-Token → #hex6 (maskPseudonym);
//         `worker_notes.text` ist backend-seitig bereits NER-maskiert (durchgereicht),
//         `maintenance_events.description` ist Sach-/SPS-Text und bleibt unmaskiert
//         (dokumentiertes Restrisiko §8 — nie als anonym deklariert).
//  Architektur-Einordnung: View-State (Schicht 2, rein).
// ============================================================
import type { MaintenanceEventRead, WorkerNoteRead } from "@/lib/api/contracts";
import { maskPseudonym } from "@/lib/ui/pii";

export type HistoryKind = "maintenance" | "note";

export interface MachineHistoryItem {
  kind: HistoryKind;
  /** Stabiler Schlüssel (kind:id) für React-Listen. */
  key: string;
  at: string;
  t: number;
  /** Hallensprache-Titel (Wartungstyp bzw. „Notiz"). */
  title: string;
  /** Klartext-Sachtext (Wartung) bzw. NER-maskierter Notiztext — nie roher Akteur. */
  body: string | null;
  /** Maskierter Akteur (#hex6) oder null — nie Klartext. */
  actorMasked: string | null;
  shift: string | null;
}

/** Vereint beide Quellen, mappt auf Historien-Items und sortiert jüngste zuerst. */
export function buildHistory(
  maintenance: readonly MaintenanceEventRead[],
  notes: readonly WorkerNoteRead[],
): MachineHistoryItem[] {
  const items: MachineHistoryItem[] = [];

  for (const event of maintenance) {
    items.push({
      kind: "maintenance",
      key: `maintenance:${event.id}`,
      at: event.performed_at,
      t: Date.parse(event.performed_at),
      title: event.type,
      body: event.description,
      actorMasked: maskPseudonym(event.performed_by),
      shift: null,
    });
  }

  for (const note of notes) {
    items.push({
      kind: "note",
      key: `note:${note.id}`,
      at: note.created_at,
      t: Date.parse(note.created_at),
      title: "Notiz",
      body: note.text,
      actorMasked: maskPseudonym(note.author),
      shift: note.shift,
    });
  }

  return items.sort((a, b) => b.t - a.t);
}
