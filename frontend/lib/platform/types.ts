// ============================================================
//  FOREMAN Frontend — lib/platform/types.ts
//  Zweck: Der Datenvertrag der Sektion I (Plattform/Audit, §22) als FE-Spiegel
//         der zwei Read-APIs (GET /api/v1/topology, GET /api/v1/audit) plus die
//         abgeleiteten View-Modelle. Roh-Felder bleiben `string` (das Backend ist
//         dort selbst nicht enum-typsicher) — die bekannten Wertemengen sind als
//         Unions deklariert, das Mapping (status.ts) defaultet defensiv auf
//         „unbekannt" (nie grün geraten). datetime kommt über JSON als ISO-String.
//  Architektur-Einordnung: View-State-Typen (Schicht 2), transport-agnostisch.
// ============================================================

/** Verbindungsstatus eines Topologie-Knotens (ehrlich abgeleitet, §22.2). */
export type ConnectionStatus = "verbunden" | "gestört" | "inaktiv" | "unbekannt";

/** Datenrichtung relativ zu FOREMAN. `keine` = [VISION], nicht verbunden. */
export type FlowDirection = "liefert" | "liest" | "beides" | "keine";

/** Knoten-Klasse der Topologie. `vision` = illustrativ, nie verbunden. */
export type NodeKind = "ingest_source" | "substrate" | "mcp_boundary" | "vision";

/** Auditierte Aktionsart (DB-CHECK: hitl_acknowledge | mcp_retrieval). */
export type AuditAction = "hitl_acknowledge" | "mcp_retrieval";

/** Herkunft des Audit-Eintrags (DB-CHECK: dashboard | mcp | system). */
export type AuditOrigin = "dashboard" | "mcp" | "system";

// ---------- Roh-Verträge (1:1-Spiegel der Backend-Schemas) ----------

/**
 * Ein Topologie-Knoten (`TopologyNode`, §22.2). `id`/`label`/`kind`/`direction`/
 * `status` sind nie null; `last_activity` ist null, wenn nie gemessen oder nicht
 * Audit-sichtbar. `internal` markiert die Simulationsquelle, `vision` ein
 * illustratives Drittsystem. `detail` variiert je `kind` (siehe Service §22.2).
 */
export interface TopologyNodeRead {
  id: string;
  label: string;
  kind: string;
  direction: string;
  status: string;
  last_activity: string | null;
  internal: boolean;
  vision: boolean;
  detail: Record<string, unknown> | null;
}

/** Die Topologie-Antwort (`TopologyView`, §22.2). */
export interface TopologyViewRead {
  nodes: TopologyNodeRead[];
  vision: TopologyNodeRead[];
  generated_at: string;
}

/**
 * Ein Audit-Eintrag (`AuditEntryRead`, §22.1). `actor` ist immer ein pseudonymer
 * HMAC-Token (nie Klartext, §8); `detail` ist PII-frei (IDs/Token, JSONB).
 */
export interface AuditEntryRead {
  id: number;
  occurred_at: string | null;
  created_at: string;
  action_type: string | null;
  actor: string | null;
  actor_role: string | null;
  origin: string | null;
  target_kind: string | null;
  target_id: number | null;
  machine_id: number | null;
  detail: Record<string, unknown> | null;
}

// ---------- Abgeleitete View-Modelle ----------

/** Knoten-Kategorie für die geordnete Darstellung (Eingänge → Substrat → Grenze). */
export type NodeCategory = "input" | "substrate" | "mcp" | "vision";

/**
 * Aufbereiteter Topologie-Knoten fürs UI: roh durchgereicht plus normalisierte
 * Kategorie. Status/Richtung werden NICHT hier gemappt (das macht `status.ts`
 * in der Komponente) — das View-Modell ordnet nur ehrlich, erfindet nichts.
 */
export interface TopologyNodeModel {
  id: string;
  label: string;
  kind: NodeKind;
  category: NodeCategory;
  status: ConnectionStatus;
  direction: FlowDirection;
  lastActivityIso: string | null;
  internal: boolean;
  isVision: boolean;
  detail: Record<string, unknown> | null;
}

/**
 * Das geordnete Topologie-Modell: reale Knoten nach Kategorie gruppiert (FOREMAN
 * im Zentrum), die [VISION]-Knoten klar getrennt. `generatedAtIso` trägt den
 * Stand der Server-Ableitung.
 */
export interface TopologyModel {
  inputs: TopologyNodeModel[];
  substrate: TopologyNodeModel[];
  mcp: TopologyNodeModel[];
  vision: TopologyNodeModel[];
  generatedAtIso: string;
}

/**
 * Eine aufbereitete Audit-Zeile: Akteur pseudonym maskiert (`#hex6`), Ziel
 * zusammengesetzt, Zeit als ISO durchgereicht (Formatierung in der Komponente).
 * `detailPairs` ist die defensiv flachgeklopfte `detail`-JSONB (nur primitive
 * Schlüssel/Werte — keine HTML-/Objekt-Injektion).
 */
export interface AuditRowModel {
  id: number;
  occurredAtIso: string | null;
  actorHandle: string | null;
  actorRole: string | null;
  actionType: string | null;
  targetKind: string | null;
  targetId: number | null;
  machineId: number | null;
  origin: string | null;
  detailPairs: ReadonlyArray<readonly [string, string]>;
}
