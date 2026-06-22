// ============================================================
//  FOREMAN Frontend — lib/platform/audit-view-model.ts
//  Zweck: Formt rohe Audit-Einträge (AuditEntryRead, §22.1) in Zeilen-Modelle.
//         Der `actor` (pseudonymer HMAC-Token) wird zu `#hex6` maskiert — NIE als
//         Klartext, NIE „aufgelöst" (Re-Identifikation lebt im QM-System, §8).
//         `detail` (JSONB) wird defensiv zu flachen Schlüssel/Wert-Strings
//         geklopft (keine tiefen Objekte, keine HTML-/eval-Pfade); React escaped
//         den Text ohnehin. Die Backend-Reihenfolge (jüngste zuerst) bleibt
//         UNANGETASTET — hier wird nicht umsortiert.
//  Architektur-Einordnung: reine Logik (Schicht 2), ohne UI testbar.
// ============================================================
import { maskPseudonym } from "@/lib/ui/pii";
import type { AuditEntryRead, AuditRowModel } from "./types";

/** Ein primitiver `detail`-Wert → kompakter String (komplexe Werte → kurzes JSON). */
function stringifyDetailValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  // Defensiv: verschachtelte Strukturen NICHT roh rendern, sondern kompakt
  // serialisieren (begrenzt) — keine HTML-/Objekt-Injektion in die Tabelle.
  try {
    const json = JSON.stringify(value);
    return json.length > 200 ? `${json.slice(0, 197)}…` : json;
  } catch {
    return "—";
  }
}

/** Flacht `detail` zu stabilen [Schlüssel, Wert]-Paaren (Eingabe-Reihenfolge). */
export function detailPairs(
  detail: Record<string, unknown> | null,
): ReadonlyArray<readonly [string, string]> {
  if (detail === null) {
    return [];
  }
  return Object.entries(detail).map(([key, value]) => [key, stringifyDetailValue(value)] as const);
}

/** Ein roher Audit-Eintrag → Zeilen-Modell (actor maskiert, detail flach). */
export function assembleAuditRow(entry: AuditEntryRead): AuditRowModel {
  return {
    id: entry.id,
    occurredAtIso: entry.occurred_at,
    actorHandle: maskPseudonym(entry.actor),
    actorRole: entry.actor_role,
    actionType: entry.action_type,
    targetKind: entry.target_kind,
    targetId: entry.target_id,
    machineId: entry.machine_id,
    origin: entry.origin,
    detailPairs: detailPairs(entry.detail),
  };
}

/** Die Liste aufbereiteter Zeilen — Reihenfolge des Backends BLEIBT (jüngste zuerst). */
export function assembleAuditRows(entries: AuditEntryRead[]): AuditRowModel[] {
  return entries.map(assembleAuditRow);
}
