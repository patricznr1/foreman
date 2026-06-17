// ============================================================
//  FOREMAN Frontend — lib/ondemand/machine.ts
//  Zweck: Der GETEILTE On-Demand-Zustandsautomat (Studie §3.2): jede erzeugte
//         Erkenntnis durchläuft sichtbar denselben Dreischritt
//         Trigger → benannter Verarbeitungszustand → Ergebnis mit Herkunft.
//         Reine, React-freie Reducer-Logik — E und die späteren On-Demand-
//         Sektionen (D/F/G/H) erben sie, statt zehn verschiedene Dialoge zu bauen.
//         Degradation (§3.2): idle/error halten ein FRÜHERES Ergebnis mit Stand
//         (kein Leerlaufen, „frühere Ergebnisse mit Datum").
//  Architektur-Einordnung: Erkenntnis-Lebenszyklus (Schicht 2), einzeln testbar.
// ============================================================

/** Ein abgerufenes On-Demand-Ergebnis samt Stand-Stempel (für ProvenanceStamp). */
export interface OnDemandResult<T> {
  data: T;
  /** ISO-Stempel des Stands. */
  stampedAt: string;
}

/**
 * Die Phasen des Dreischritts. `idle` ist der Ruhezustand (leer ODER ein früheres
 * Ergebnis mit Stand); `processing` der benannte Verarbeitungszustand; `result`
 * das frische Ergebnis; `error` ein Fehlschlag, der ein etwaiges früheres Ergebnis
 * NICHT verwirft (Degradation friert ein).
 */
export type OnDemandPhase<T> =
  | { kind: "idle"; previous: OnDemandResult<T> | null }
  | { kind: "processing"; previous: OnDemandResult<T> | null }
  | { kind: "result"; result: OnDemandResult<T> }
  | { kind: "error"; message: string; previous: OnDemandResult<T> | null };

/** Ereignisse, die den Automaten weiterschalten. */
export type OnDemandEvent<T> =
  | { type: "request" }
  | { type: "resolve"; data: T; stampedAt: string }
  | { type: "reject"; message: string }
  | { type: "reset" };

/** Startphase: leer oder mit einem geladenen früheren Ergebnis. */
export function initialPhase<T>(previous: OnDemandResult<T> | null = null): OnDemandPhase<T> {
  return { kind: "idle", previous };
}

/** Das aktuell anzeigbare frühere Ergebnis (für „frühere Ergebnisse mit Stand"). */
export function previousResult<T>(phase: OnDemandPhase<T>): OnDemandResult<T> | null {
  switch (phase.kind) {
    case "result":
      return phase.result;
    case "idle":
    case "processing":
    case "error":
      return phase.previous;
  }
}

/**
 * Reiner Reducer. `request` schaltet in den Verarbeitungszustand und behält das
 * frühere Ergebnis (damit die Sicht beim Triggern nicht weiß wird). `resolve`
 * legt das frische Ergebnis hin; `reject` zeigt den Fehler, ohne das frühere
 * Ergebnis zu verlieren; `reset` kehrt in den Ruhezustand zurück (Ergebnis bleibt
 * als „früher" erhalten).
 */
export function onDemandReducer<T>(
  phase: OnDemandPhase<T>,
  event: OnDemandEvent<T>,
): OnDemandPhase<T> {
  switch (event.type) {
    case "request":
      return { kind: "processing", previous: previousResult(phase) };
    case "resolve":
      return { kind: "result", result: { data: event.data, stampedAt: event.stampedAt } };
    case "reject":
      return { kind: "error", message: event.message, previous: previousResult(phase) };
    case "reset":
      return { kind: "idle", previous: previousResult(phase) };
  }
}
