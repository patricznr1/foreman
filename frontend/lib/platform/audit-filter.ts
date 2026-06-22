// ============================================================
//  FOREMAN Frontend — lib/platform/audit-filter.ts
//  Zweck: Reiner Filter-/Pagination-Zustand der Audit-Tabelle und seine
//         defensive Übersetzung in die REALEN Query-Parameter von GET /api/v1/audit
//         (action_type/target_kind/target_id/actor/machine_id/since/until/limit/
//         offset, §22.1). Leere/ungültige Felder fallen heraus (keine erfundenen
//         Parameter); limit wird auf den Backend-Bereich 1..1000 geklemmt, offset
//         auf ≥ 0. Ohne UI testbar.
//  Architektur-Einordnung: reine Logik (Schicht 2).
// ============================================================
import type { AuditAction } from "./types";

/** Untere/obere Grenzen aus dem Backend-Vertrag (§22.1). */
export const AUDIT_LIMIT_MIN = 1;
export const AUDIT_LIMIT_MAX = 1000;
export const AUDIT_DEFAULT_PAGE_SIZE = 50;

/** Die im Backend-CHECK erlaubten Aktionsarten — Quelle für das Filter-Select. */
export const AUDIT_ACTIONS: readonly AuditAction[] = ["hitl_acknowledge", "mcp_retrieval"];

/**
 * Der Filter-/Seiten-Zustand der Audit-Sicht. Strings sind „roh aus dem
 * Eingabefeld" (leer = nicht gesetzt); Zahlen sind null, wenn nicht gesetzt.
 * `since`/`until` tragen den vom Eingabefeld gelieferten ISO-/Datetime-Wert.
 */
export interface AuditFilter {
  actionType: AuditAction | null;
  targetKind: string;
  targetId: number | null;
  actor: string;
  machineId: number | null;
  since: string;
  until: string;
  limit: number;
  offset: number;
}

/** Der leere Anfangszustand (jüngste Seite, keine Filter). */
export function emptyAuditFilter(): AuditFilter {
  return {
    actionType: null,
    targetKind: "",
    targetId: null,
    actor: "",
    machineId: null,
    since: "",
    until: "",
    limit: AUDIT_DEFAULT_PAGE_SIZE,
    offset: 0,
  };
}

/** Klemmt das Limit defensiv in den vom Backend akzeptierten Bereich. */
export function clampLimit(limit: number): number {
  if (!Number.isFinite(limit)) {
    return AUDIT_DEFAULT_PAGE_SIZE;
  }
  const rounded = Math.trunc(limit);
  if (rounded < AUDIT_LIMIT_MIN) {
    return AUDIT_LIMIT_MIN;
  }
  if (rounded > AUDIT_LIMIT_MAX) {
    return AUDIT_LIMIT_MAX;
  }
  return rounded;
}

/** Klemmt den Offset auf ≥ 0 (ganzzahlig). */
export function clampOffset(offset: number): number {
  if (!Number.isFinite(offset) || offset < 0) {
    return 0;
  }
  return Math.trunc(offset);
}

function trimmed(value: string): string | null {
  const out = value.trim();
  return out.length > 0 ? out : null;
}

function positiveInt(value: number | null): number | null {
  if (value === null || !Number.isInteger(value) || value <= 0) {
    return null;
  }
  return value;
}

/**
 * Übersetzt den Filter in die gesetzten Query-Parameter-Paare (Reihenfolge stabil).
 * Nur tatsächlich gesetzte, gültige Felder erscheinen — limit/offset immer.
 */
export function auditQueryEntries(filter: AuditFilter): Array<[string, string]> {
  const entries: Array<[string, string]> = [];
  if (filter.actionType !== null) {
    entries.push(["action_type", filter.actionType]);
  }
  const targetKind = trimmed(filter.targetKind);
  if (targetKind !== null) {
    entries.push(["target_kind", targetKind]);
  }
  const targetId = positiveInt(filter.targetId);
  if (targetId !== null) {
    entries.push(["target_id", String(targetId)]);
  }
  const actor = trimmed(filter.actor);
  if (actor !== null) {
    entries.push(["actor", actor]);
  }
  const machineId = positiveInt(filter.machineId);
  if (machineId !== null) {
    entries.push(["machine_id", String(machineId)]);
  }
  const since = trimmed(filter.since);
  if (since !== null) {
    entries.push(["since", since]);
  }
  const until = trimmed(filter.until);
  if (until !== null) {
    entries.push(["until", until]);
  }
  entries.push(["limit", String(clampLimit(filter.limit))]);
  entries.push(["offset", String(clampOffset(filter.offset))]);
  return entries;
}

/** Wie viele der nicht-Pagination-Filter aktiv sind (für „Filter zurücksetzen"-UX). */
export function activeFilterCount(filter: AuditFilter): number {
  return auditQueryEntries(filter).filter(([key]) => key !== "limit" && key !== "offset").length;
}
