// ============================================================
//  FOREMAN Frontend — lib/capture/outbox.ts
//  Zweck: Die bewusste Offline-Schreib-Queue (Studie §4J: „lokal sofort
//         gespeichert, synchronisiert nachträglich"). DATENSCHUTZ (§8): hält den
//         vom Werker eingegebenen Klartext NUR bis zum erfolgreichen Senden — danach
//         wird das Item gelöscht (removeFromOutbox). KEIN dauerhafter Klartext-PII-
//         Cache, der die serverseitige NER-Maskierung umginge. localStorage (damit
//         eine offline geschriebene Notiz einen Tab-/Browser-Neustart überlebt),
//         eigener Namespace-Key, alles best-effort (Speicher gesperrt/voll → die
//         Erfassung läuft trotzdem, nur ohne Puffer-Persistenz).
//  Architektur-Einordnung: Persistenz-Naht (Schicht 1). Storage injizierbar (Tests).
// ============================================================
import type { WorkerNoteCreate } from "@/lib/api/contracts";
import type { QueuedNote } from "./types";

/** Namespace-Konvention „foreman.<bereich>.<zweck>" (vgl. memory.lastSearch). */
export const OUTBOX_KEY = "foreman.notes.outbox";

/** localStorage, SSR-/Privacy-Sandbox-sicher (kein Zugriff → null, Queue inaktiv). */
function defaultStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Eindeutige lokale ID (crypto.randomUUID in Browser + Node 24; sonst Fallback). */
function defaultId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `local-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e9).toString(36)}`;
}

/** Validiert ein rohes Item gegen QueuedNote (corrupted storage → verworfen). */
function isQueuedNote(value: unknown): value is QueuedNote {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const item = value as Record<string, unknown>;
  const payload = item.payload as Record<string, unknown> | undefined;
  return (
    typeof item.localId === "string" &&
    typeof item.enqueuedAt === "string" &&
    typeof payload === "object" &&
    payload !== null &&
    typeof payload.text === "string"
  );
}

/** Liest die Queue. Fehlende/kaputte Daten ergeben eine leere Queue (nie throw). */
export function readOutbox(storage: Storage | null = defaultStorage()): QueuedNote[] {
  if (!storage) {
    return [];
  }
  try {
    const raw = storage.getItem(OUTBOX_KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isQueuedNote);
  } catch {
    return [];
  }
}

/** Schreibt die Queue zurück (best-effort; Speicher voll/gesperrt → still). */
export function writeOutbox(notes: QueuedNote[], storage: Storage | null = defaultStorage()): void {
  if (!storage) {
    return;
  }
  try {
    if (notes.length === 0) {
      storage.removeItem(OUTBOX_KEY);
      return;
    }
    storage.setItem(OUTBOX_KEY, JSON.stringify(notes));
  } catch {
    // Speicher gesperrt/voll — die Erfassung läuft auch ohne persistenten Puffer.
  }
}

/** Hängt eine Notiz an die Queue an und gibt das gepufferte Item zurück. */
export function enqueueNote(
  payload: WorkerNoteCreate,
  options: { storage?: Storage | null; makeId?: () => string; now?: () => string } = {},
): QueuedNote {
  const storage = options.storage ?? defaultStorage();
  const item: QueuedNote = {
    localId: (options.makeId ?? defaultId)(),
    payload,
    enqueuedAt: (options.now ?? (() => new Date().toISOString()))(),
  };
  const next = [...readOutbox(storage), item];
  writeOutbox(next, storage);
  return item;
}

/**
 * Entfernt ein Item NACH erfolgreichem Senden (oder hartem, nicht-retrybarem
 * Fehler) — der eigentliche Datenschutz-Hebel: Klartext liegt nur bis hierher.
 * Gibt die verbleibende Queue zurück.
 */
export function removeFromOutbox(
  localId: string,
  storage: Storage | null = defaultStorage(),
): QueuedNote[] {
  const next = readOutbox(storage).filter((item) => item.localId !== localId);
  writeOutbox(next, storage);
  return next;
}

/** Leert die Queue vollständig. */
export function clearOutbox(storage: Storage | null = defaultStorage()): void {
  writeOutbox([], storage);
}

/** Anzahl ausstehender Notizen (für die Sync-Status-Anzeige). */
export function outboxCount(storage: Storage | null = defaultStorage()): number {
  return readOutbox(storage).length;
}
