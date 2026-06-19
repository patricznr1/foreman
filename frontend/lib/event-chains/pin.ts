// ============================================================
//  FOREMAN Frontend — lib/event-chains/pin.ts
//  Zweck: Anpinnen einer gespeicherten Kette an die Maschinen-Zeitachse (B,
//         Studie §4D). Der Pin trägt einen EINGEFRORENEN Stand-Stempel (der
//         Erstellzeitpunkt der Kette) — er friert „Stand X" ein, auch wenn sich
//         die Quelldaten ändern. Persistenz client-seitig (localStorage), Storage
//         injizierbar → ohne Browser testbar. Schreibweg liegt in D, Lesepfad in B.
//  Architektur-Einordnung: reine Persistenz-Logik (Schicht 2).
// ============================================================
import type { ConfidenceLevel } from "./types";

const PIN_KEY = "foreman.chains.pinned";

/** Minimaler Storage-Vertrag (Teilmenge von Web Storage) — injizierbar für Tests. */
export interface PinStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/** Eine angepinnte Kette — als Momentaufnahme mit eingefrorenem Stand. */
export interface PinnedChain {
  explanationId: number;
  machineId: number;
  anchorAlarmId: number;
  confidence: ConfidenceLevel;
  isHypothesis: boolean;
  eventCount: number;
  /** Eingefrorener Stand-Stempel (ISO) — der Erstellzeitpunkt der Kette. */
  stampedAt: string;
  /** Zeitpunkt des Anpinnens (ISO, vom Aufrufer gestempelt — kein Date.now hier). */
  pinnedAt: string;
}

/** Fällt im SSR/Test-Kontext ohne echtes localStorage auf einen No-op zurück. */
function resolveStorage(storage?: PinStorage): PinStorage | null {
  if (storage) {
    return storage;
  }
  if (typeof window !== "undefined" && window.localStorage) {
    return window.localStorage;
  }
  return null;
}

function readAll(storage: PinStorage): PinnedChain[] {
  const raw = storage.getItem(PIN_KEY);
  if (raw === null) {
    return [];
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as PinnedChain[]) : [];
  } catch {
    return [];
  }
}

function writeAll(storage: PinStorage, items: PinnedChain[]): void {
  storage.setItem(PIN_KEY, JSON.stringify(items));
}

/** Pinnt eine Kette an ihre Maschine (idempotent über explanationId). */
export function pinChain(pin: PinnedChain, storage?: PinStorage): void {
  const resolved = resolveStorage(storage);
  if (resolved === null) {
    return;
  }
  const existing = readAll(resolved).filter((item) => item.explanationId !== pin.explanationId);
  writeAll(resolved, [pin, ...existing]);
}

/** Entfernt einen Pin (über explanationId). */
export function unpinChain(explanationId: number, storage?: PinStorage): void {
  const resolved = resolveStorage(storage);
  if (resolved === null) {
    return;
  }
  writeAll(
    resolved,
    readAll(resolved).filter((item) => item.explanationId !== explanationId),
  );
}

/** Alle für eine Maschine angepinnten Ketten (jüngste zuerst). */
export function readPinnedChains(machineId: number, storage?: PinStorage): PinnedChain[] {
  const resolved = resolveStorage(storage);
  if (resolved === null) {
    return [];
  }
  return readAll(resolved)
    .filter((item) => item.machineId === machineId)
    .sort((a, b) => b.pinnedAt.localeCompare(a.pinnedAt));
}

/** Ob eine bestimmte Kette bereits angepinnt ist. */
export function isPinned(explanationId: number, storage?: PinStorage): boolean {
  const resolved = resolveStorage(storage);
  if (resolved === null) {
    return false;
  }
  return readAll(resolved).some((item) => item.explanationId === explanationId);
}
