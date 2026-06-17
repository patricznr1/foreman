// ============================================================
//  FOREMAN Frontend — lib/capture/shifts.ts
//  Zweck: Die drei Standard-Schichten als Auswahl-Chips (Studie §4J: Zuordnung
//         per Chip statt Dropdown-Suche). Reine FRONTEND-Konvention — das Backend
//         nimmt `shift` als Freitext (≤ 16 Zeichen, kein Enum); die Werte bleiben
//         bewusst unter der Längengrenze. Schicht ist OPTIONAL (eine Notiz ohne
//         Schicht ist erlaubt).
//  Architektur-Einordnung: Erfassungs-Logik (Schicht 2). Reine Logik, testbar.
// ============================================================

export interface ShiftOption {
  /** Wert, der ans Backend geht (≤ 16 Zeichen). */
  value: string;
  /** Kurzes Chip-Label (Hallensprache). */
  label: string;
}

export const SHIFTS: readonly ShiftOption[] = [
  { value: "Frühschicht", label: "Früh" },
  { value: "Spätschicht", label: "Spät" },
  { value: "Nachtschicht", label: "Nacht" },
];

/** Backend-Längengrenze für `shift` (api/routers/worker_notes.py: max_length=16). */
export const SHIFT_MAX_LENGTH = 16;
