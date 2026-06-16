// ============================================================
//  FOREMAN Frontend — lib/state/view-state.ts
//  Zweck: Die ABGELEITETE View-State-Ebene (Studie §5.1, Ebene 2): leitet aus
//         Stream-View + Verbindungsstatus die FÜNF Pflichtzustände ab
//         (live / gecacht / lädt / leer / Fehler, Prinzip 2 / §5.5). Reine
//         Funktion, ohne React — überall identisch, einzeln testbar.
//         Degradation friert ein: geladen + Verbindung weg → gecacht, NICHT leer.
//  Architektur-Einordnung: State-Ebene 2 (abgeleitet, memoisierbar).
// ============================================================
import type { TopicView } from "../realtime/realtime-store";
import type { ConnectionStatus } from "../realtime/transport";

export type DataState<T> =
  | { kind: "loading" }
  | { kind: "live"; data: T }
  | { kind: "cached"; data: T }
  | { kind: "empty" }
  | { kind: "error"; message: string };

export interface DeriveOptions<T> {
  /** Entscheidet, ob geladene Daten als „leer" gelten (z. B. leere Liste). */
  isEmpty?: (data: T) => boolean;
}

/** Fehler, die einen harten Fehlerzustand erzwingen (auch bei vorhandenem Cache). */
const FATAL_ERRORS: ReadonlySet<string> = new Set(["forbidden", "unauthorized"]);

export function deriveDataState<T>(
  view: TopicView,
  status: ConnectionStatus,
  options: DeriveOptions<T> = {},
): DataState<T> {
  const { data, error, loaded } = view;

  // Autoritativer Fehler (z. B. Zugriff entzogen) — schlägt Cache.
  if (error !== null && FATAL_ERRORS.has(error)) {
    return { kind: "error", message: error };
  }

  if (!loaded) {
    if (error !== null) {
      return { kind: "error", message: error };
    }
    return { kind: "loading" };
  }

  const typed = data as T;
  // Defensiv: geladen, aber kein Inhalt (Upstream lieferte null/undefined) → leer.
  if (typed === undefined || typed === null) {
    return { kind: "empty" };
  }
  const empty = options.isEmpty ? options.isEmpty(typed) : false;
  if (empty) {
    return { kind: "empty" };
  }

  if (status === "open") {
    return { kind: "live", data: typed };
  }
  // Geladen, aber Verbindung weg → eingefroren (gecacht), nicht geleert.
  return { kind: "cached", data: typed };
}
