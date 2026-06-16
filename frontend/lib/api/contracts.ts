// ============================================================
//  FOREMAN Frontend — lib/api/contracts.ts
//  Zweck: TypeScript-Spiegel des REALEN Backend-Vertrags (F5). Gegen den
//         tatsächlichen Vertrag typisiert, nicht gegen Annahmen:
//         GET /api/v1/overview · /machines/{id}/trend · /me · WS /api/v1/ws.
//  Architektur-Einordnung: Transport-Vertrag (Schicht 1). Wächst pro Sektion.
//  Quelle: GROUND_TRUTH §4/§20 + schemas/dashboard.py + realtime/ws.py.
// ============================================================

/** Komponierter Maschinenstatus (reads/status.py:compose_status). */
export type MachineStatus = "healthy" | "drift_active" | "open_warning";

/** Backend-Rollen (DB-IDs englisch). UI-Labels sind deutsch (Hallensprache). */
export type Role = "worker" | "shift_lead" | "technician" | "manager";

export interface MachineStatusOut {
  id: number;
  label: string;
  line_id: number | null;
  machine_class: string | null;
  status: MachineStatus;
  open_alarm_count: number;
  /** z. B. { "warning": 2, "critical": 1 } — nur für Aggregat, nicht der Leitwert. */
  open_by_severity: Record<string, number>;
  last_alarm_at: string | null; // ISO 8601
}

export interface FleetOverviewOut {
  machines: MachineStatusOut[];
  by_status: Record<MachineStatus, number>;
  open_alarm_total: number;
}

export interface TrendPointOut {
  bucket: string; // ISO 8601, Minuten-Bucket
  avg: number;
  min: number;
  max: number;
  last: number | null;
}

export interface MachineTrendOut {
  machine_id: number;
  data_point_id: number;
  data_point_name: string;
  unit: string | null;
  measurement_type: string | null;
  normal_min: number | null;
  normal_max: number | null;
  points: TrendPointOut[];
  truncated: boolean;
  profile_band: null; // reserviert (F4-Eigenprofil folgt) — derzeit immer null
}

/** GET /api/v1/me — Identität + Rolle + Per-User-Scope (Spiegel der Server-Authz). */
export interface CurrentUser {
  id: number;
  email: string;
  role: Role;
  assigned_line_ids: number[];
  assigned_machine_ids: number[];
}

// — WebSocket-Vertrag (/api/v1/ws) — ein gemultiplexter Kanal, Themen-Abos. —

/** Topic-Strings: "overview" | "machine:{id}" | "trend:{data_point_id}". */
export type WsTopic = "overview" | `machine:${number}` | `trend:${number}`;

/** Client → Server. */
export interface WsClientMessage {
  action: "subscribe" | "unsubscribe";
  topic: string;
}

/** Server → Client: { type, topic, data } bei Erfolg, { type:"error", reason } bei Deny. */
export interface WsServerMessage {
  type: "update" | "error";
  topic: string;
  data?: unknown;
  reason?: string;
}

/** WS-Close-Code bei fehlendem/ungültigem Token (realtime/ws.py). */
export const WS_UNAUTHORIZED_CLOSE = 4401;
