// ============================================================
//  FOREMAN Frontend — lib/capture/shifts.ts
//  Zweck: Die drei Standard-Schichten als Auswahl-Chips (Studie §4J: Zuordnung
//         per Chip statt Dropdown-Suche). Das Backend nimmt `shift` als Freitext
//         (≤ 16 Zeichen, kein Enum); die Werte bleiben bewusst unter der
//         Längengrenze. Schicht ist OPTIONAL (eine Notiz ohne Schicht ist erlaubt).
//  DER WERT IST KEINE FRONTEND-KONVENTION, auch wenn er hier steht: Er landet
//         unverändert in `worker_notes.shift` und wandert von dort ins
//         Gedächtnis. Der Bestand — Adapter-Weg, Szenario-Konfiguration, Tests —
//         führt durchgehend `frueh`/`spaet`/`nacht`. Stünde hier eine zweite
//         Schreibweise, gäbe es für drei Schichten sechs Bezeichner, und jede
//         Gruppierung über die Schicht zerfiele in zwei Hälften, die keine Suche
//         mehr zusammenbringt. Sichtbar wird das nirgends: Die Notiz wird
//         gespeichert, die Oberfläche zeigt das Label, und erst eine Auswertung
//         über den Bestand stolpert darüber.
//         Das Label ist die Halle, der Wert ist der Bestand — die beiden sind
//         deshalb getrennt.
//  Architektur-Einordnung: Erfassungs-Logik (Schicht 2). Reine Logik, testbar.
// ============================================================

export interface ShiftOption {
  /** Wert, der ans Backend geht und im Bestand landet (≤ 16 Zeichen). */
  value: string;
  /** Kurzes Chip-Label (Hallensprache) — frei änderbar, ohne den Bestand zu berühren. */
  label: string;
}

export const SHIFTS: readonly ShiftOption[] = [
  { value: "frueh", label: "Früh" },
  { value: "spaet", label: "Spät" },
  { value: "nacht", label: "Nacht" },
];

/** Backend-Längengrenze für `shift` (api/routers/worker_notes.py: max_length=16). */
export const SHIFT_MAX_LENGTH = 16;
