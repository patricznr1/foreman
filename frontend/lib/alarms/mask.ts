// ============================================================
//  FOREMAN Frontend — lib/alarms/mask.ts
//  Zweck: PII-Maskierung von `acknowledged_by` (§8). Das Backend liefert einen
//         HMAC-Token „v{n}:{hex}" — nie Klartext. Das Frontend zeigt ausschließlich
//         eine kurze pseudonyme Form (#hex6). Niemals den vollen Token, niemals
//         eine aufgelöste Identität (die existiert client-seitig gar nicht).
//  Architektur-Einordnung: Reine Ableitung (Schicht 2). Ohne UI testbar.
// ============================================================

/**
 * HMAC-Token → kurzes pseudonymes Handle (#hex6). `null`/leer → null.
 * Der Versions-Präfix („v1:") wird abgetrennt; aus dem Digest bleiben die ersten
 * 6 Hex-Zeichen als Wiedererkennungs-Handle — auditierbar (Behörde kann den vollen
 * Token verifizieren), aber kein Klartext.
 */
export function maskAcknowledgedBy(token: string | null | undefined): string | null {
  if (!token) {
    return null;
  }
  const separator = token.indexOf(":");
  const digest = separator >= 0 ? token.slice(separator + 1) : token;
  const hex = digest.replace(/[^a-fA-F0-9]/g, "").slice(0, 6).toLowerCase();
  return hex.length > 0 ? `#${hex}` : "#anonym";
}

/** „quittiert von #a7f3e8 um 14:07" (oder null, wenn nicht quittiert). */
export function acknowledgedByLabel(
  token: string | null | undefined,
  atIso: string | null | undefined,
): string | null {
  const masked = maskAcknowledgedBy(token);
  if (masked === null) {
    return null;
  }
  const time = formatTime(atIso);
  return time ? `quittiert von ${masked} um ${time}` : `quittiert von ${masked}`;
}

function formatTime(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}
