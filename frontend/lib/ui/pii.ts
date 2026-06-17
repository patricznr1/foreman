// ============================================================
//  FOREMAN Frontend — lib/ui/pii.ts
//  Zweck: Geteilte PII-Maskierung. Werker-bezogene Felder kommen als HMAC-Token
//         "v{n}:{hex}" über die API (§8, pseudonymisiert, nie Klartext) — das UI
//         zeigt nur ein kurzes, wiedererkennbares #hex6-Handle (auditierbar, aber
//         kein Klartext). Kanonischer Primitive für Sektion B (Historie); die
//         ältere alarm-spezifische maskAcknowledgedBy (lib/alarms/mask.ts) kann
//         später hierauf delegieren (Vereinheitlichungs-Naht, bewusst offen).
//  Architektur-Einordnung: UI-Helfer (Schicht 2/3, rein).
// ============================================================

/** HMAC-Pseudonym-Token → "#hex6". Versions-Präfix ("v1:") entfällt. null/leer → null. */
export function maskPseudonym(token: string | null | undefined): string | null {
  if (!token) {
    return null;
  }
  const separator = token.indexOf(":");
  const digest = separator >= 0 ? token.slice(separator + 1) : token;
  const hex = digest
    .replace(/[^a-fA-F0-9]/g, "")
    .slice(0, 6)
    .toLowerCase();
  return hex.length > 0 ? `#${hex}` : null;
}
