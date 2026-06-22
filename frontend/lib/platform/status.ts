// ============================================================
//  FOREMAN Frontend — lib/platform/status.ts
//  Zweck: Mehrkanaliges Mapping des Verbindungsstatus (verbunden/gestört/inaktiv/
//         unbekannt) und der Datenrichtung (liefert/liest/beides/keine) auf eine
//         RUHIGE, ISA-101-konforme Darstellung (Farbe-Token + Form/Glyph + Label),
//         NICHT FCSM (das Atom StatusIndicator ist maschinen-zustands-typisiert und
//         kennt kein „unbekannt"). Bedeutung trägt mehr als Farbe: ein gestörter
//         Knoten ist klar, aber kein Alarm-Drama; „unbekannt" bleibt ehrlich neutral
//         (nie grün). Jeder fremde/leere Roh-Wert defaultet defensiv auf „unbekannt".
//  Architektur-Einordnung: reine Logik (Schicht 2), ohne UI testbar.
// ============================================================
import type { ConnectionStatus, FlowDirection } from "./types";

/** Form-Kanal des Status (farbunabhängig lesbar). */
export type StatusGlyph = "filled" | "warning" | "hollow" | "question";

/**
 * Präsentation eines Verbindungsstatus. `colorToken` ist ein semantischer Token
 * (für `var(--color-*)` im SVG und für `bg-*`-Utilities), `glyph` der
 * farbunabhängige Form-Kanal, `label` die Hallensprache.
 */
export interface StatusPresentation {
  status: ConnectionStatus;
  colorToken: string;
  glyph: StatusGlyph;
  label: string;
  /** Ruhiger Beschreibungstext (Tooltip/aria) — erklärt den Zustand ehrlich. */
  description: string;
}

const CONNECTION_STATUSES: ReadonlySet<string> = new Set([
  "verbunden",
  "gestört",
  "inaktiv",
  "unbekannt",
]);

/** Normalisiert einen Roh-Status; alles Unerwartete wird ehrlich „unbekannt". */
export function normalizeStatus(raw: string | null | undefined): ConnectionStatus {
  if (raw != null && CONNECTION_STATUSES.has(raw)) {
    return raw as ConnectionStatus;
  }
  return "unbekannt";
}

const STATUS_PRESENTATION: Record<ConnectionStatus, StatusPresentation> = {
  // Verbunden: jüngste Aktivität im Frischefenster — die einzige „grüne" Aussage.
  verbunden: {
    status: "verbunden",
    colorToken: "state-ok",
    glyph: "filled",
    label: "verbunden",
    description: "Verbindung aktiv — jüngste Aktivität im Frischefenster.",
  },
  // Gestört: konfiguriert, aber Probe/Erwartung fehlgeschlagen. Ruhig (orange),
  // KEIN Alarm-Rot — Admin-Lagebild, kein Hallenalarm.
  gestört: {
    status: "gestört",
    colorToken: "state-check",
    glyph: "warning",
    label: "gestört",
    description: "Konfiguriert, aber die Prüfung schlug fehl.",
  },
  // Inaktiv: konfiguriert, aber keine Aktivität im Fenster — neutral, kein Alarm.
  inaktiv: {
    status: "inaktiv",
    colorToken: "fg-muted",
    glyph: "hollow",
    label: "inaktiv",
    description: "Konfiguriert, aber ohne jüngste Aktivität.",
  },
  // Unbekannt: nicht gemessen. Ehrlich neutral — NIE als „ok" geraten.
  unbekannt: {
    status: "unbekannt",
    colorToken: "fg-muted",
    glyph: "question",
    label: "unbekannt",
    description: "Nicht messbar — der Zustand bleibt offen.",
  },
};

/** Die Darstellung eines (roh oder bereits normalisierten) Status. */
export function statusPresentation(raw: string | null | undefined): StatusPresentation {
  return STATUS_PRESENTATION[normalizeStatus(raw)];
}

/** Pfeil-Kanal der Datenrichtung (Form, nicht Farbe). */
export type DirectionArrow = "in" | "out" | "both" | "none";

/**
 * Präsentation der Datenrichtung. `arrow` ist der Form-Kanal (Pfeilrichtung
 * relativ zu FOREMAN), `label` die Hallensprache, `description` der Klartext.
 */
export interface DirectionPresentation {
  direction: FlowDirection;
  arrow: DirectionArrow;
  label: string;
  description: string;
}

const FLOW_DIRECTIONS: ReadonlySet<string> = new Set(["liefert", "liest", "beides", "keine"]);

/** Normalisiert eine Roh-Richtung; Unerwartetes wird zu „keine" (kein erfundener Fluss). */
export function normalizeDirection(raw: string | null | undefined): FlowDirection {
  if (raw != null && FLOW_DIRECTIONS.has(raw)) {
    return raw as FlowDirection;
  }
  return "keine";
}

const DIRECTION_PRESENTATION: Record<FlowDirection, DirectionPresentation> = {
  liefert: {
    direction: "liefert",
    arrow: "in",
    label: "liefert",
    description: "Quelle liefert Daten an FOREMAN.",
  },
  liest: {
    direction: "liest",
    arrow: "out",
    label: "liest",
    description: "FOREMAN liest aus dieser Schnittstelle.",
  },
  beides: {
    direction: "beides",
    arrow: "both",
    label: "beides",
    description: "Austausch in beide Richtungen.",
  },
  keine: {
    direction: "keine",
    arrow: "none",
    label: "keine",
    description: "Nicht verbunden.",
  },
};

/** Die Darstellung einer (roh oder normalisierten) Datenrichtung. */
export function directionPresentation(raw: string | null | undefined): DirectionPresentation {
  return DIRECTION_PRESENTATION[normalizeDirection(raw)];
}
