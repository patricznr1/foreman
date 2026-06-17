// ============================================================
//  FOREMAN Frontend — lib/ui/cx.ts
//  Zweck: Winziger Klassen-Joiner (bedingte Tailwind-Klassen).
// ============================================================
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
