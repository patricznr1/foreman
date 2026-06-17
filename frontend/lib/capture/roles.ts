// ============================================================
//  FOREMAN Frontend — lib/capture/roles.ts
//  Zweck: Rollen-Varianten der Erfassung (Studie §3.1 Matrix + §4J): Werker =
//         primäre, geführte Erfassung (größte Ziele, Sprache zuerst angeboten);
//         Techniker = mobil/einhändig erfassen; Schichtleiter = erfassen + frühere
//         Notizen sichten; Manager = liest, erfasst NICHT (reduzierte Ansicht).
//         Sichtbarkeit ≤ Server-Guard (requireSection("J")) — der Server bleibt
//         die Autorität (§20.4); das hier ist die UX-Ausprägung.
//  Architektur-Einordnung: Zugriffs-Spiegel (Schicht 2). Reine Logik, testbar.
// ============================================================
import type { Role } from "@/lib/api/contracts";

export interface CaptureRoleView {
  /** Darf erfassen (Formular sichtbar)? Manager liest nur. */
  canCapture: boolean;
  /** Sprache zuerst angeboten (Werker — der [VISION]-Hinweis steht prominenter). */
  voiceFirst: boolean;
  /** Dezente Kontextvorschläge (frühere Fälle an dieser Maschine, Brücke zu H)? */
  showSuggestions: boolean;
  /** Reduzierte Lese-/Hinweis-Ansicht statt Erfassung (Manager, default-deny). */
  readOnly: boolean;
}

const ROLE_VIEW: Record<Role, CaptureRoleView> = {
  // Werker: Kernnutzer, einfachster Pfad, Sprache zuerst angeboten.
  worker: { canCapture: true, voiceFirst: true, showSuggestions: true, readOnly: false },
  // Schichtleiter: erfasst über Bereiche + sichtet frühere Notizen.
  shift_lead: { canCapture: true, voiceFirst: false, showSuggestions: true, readOnly: false },
  // Techniker: mobil/einhändig erfassen, technische Notiz mit Detail.
  technician: { canCapture: true, voiceFirst: false, showSuggestions: true, readOnly: false },
  // Manager: liest, erfasst nicht (reduziert).
  manager: { canCapture: false, voiceFirst: false, showSuggestions: false, readOnly: true },
};

/** Restriktivster Default für unbekannte Backend-Rollen (default-deny → nur lesen). */
const DENY_VIEW: CaptureRoleView = {
  canCapture: false,
  voiceFirst: false,
  showSuggestions: false,
  readOnly: true,
};

export function captureRoleView(role: Role): CaptureRoleView {
  return ROLE_VIEW[role] ?? DENY_VIEW;
}
