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

// — Alarm-Vertrag (Sektion C) — gegen den REALEN Code, nicht gegen Annahmen.
//   Quelle: schemas/resources.py (AlarmRead/AlarmSeverity), api/routers/alarms.py,
//   reasoners/drift/router.py. Severity ist 5-stufig (NICHT kritisch/hoch/…); die
//   ISA-18.2-Prioritäts-Staffelung leitet das Frontend ab (lib/alarms/priority.ts).

/** Backend-Alarm-Severity (schemas/resources.py:23). */
export type AlarmSeverity = "info" | "warning" | "alarm" | "critical" | "emergency";

/**
 * Ein Alarm inkl. Drift-Warnung (GET /api/v1/alarms · AlarmRead). Lebenszyklus
 * trägt KEIN eigenes Feld — er wird aus den Zeitstempeln abgeleitet:
 * `cleared_at` gesetzt → geklärt; sonst `acknowledged_at` gesetzt → quittiert;
 * sonst aktiv. `acknowledged_by` ist ein HMAC-Token (§8), nie Klartext —
 * das Frontend zeigt nur die maskierte Form.
 */
export interface AlarmRead {
  id: number;
  machine_id: number;
  component_id: number | null;
  data_point_id: number | null;
  /** z. B. "DRIFT" für Drift-Warnungen (eigene, weichere Klasse). */
  code: string | null;
  message: string | null;
  /** Roh-String; das Backend liefert AlarmSeverity, defensiv als string typisiert. */
  severity: string;
  category: string;
  raised_at: string; // ISO 8601
  cleared_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null; // HMAC-Token "v{n}:{hex}", nie Klartext
  created_at: string;
}

/** Drift-Warnungen (code=DRIFT) tragen genau diesen Backend-Code. */
export const DRIFT_ALARM_CODE = "DRIFT";

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

// — Ausfallvorhersage & Empfehlung (Sektion E) — gegen den REALEN Code typisiert.
//   Quelle: reasoners/failure/schema.py (FailurePredictionRead, TopFactor,
//   WorkerRecommendationRead, validation_caveat_for), reasoners/failure/router.py.
//   KERN-INVARIANTE (§16): validation_status/data_regime/validation_caveat sind
//   PFLICHT (kein Default, Literal, DB-CHECK) — eine Vorhersage/Empfehlung kann
//   nicht ohne ihren Sim-Vorbehalt existieren. Das Frontend führt diese Garantie
//   als Negativ-Guard fort (fehlt der Vorbehalt → Fehler-Zustand, nie nackte Zahl).

/** Wirkrichtung eines Einflussfaktors (assoziativ, NICHT kausal — Model Card). */
export type FactorDirection = "increases_risk" | "decreases_risk";

/** Operative Entscheidung relativ zum kostensensitiven Schwellwert. */
export type RiskDecision = "elevated_risk" | "normal";

/** Der Sim-Vorbehalt: einziger erlaubter Wert (Pflichtfeld, §16). */
export type ValidationStatus = "simulation_only";

/** Datenregime des Trainings: ausschließlich Simulation. */
export type DataRegime = "simulation";

/**
 * Ein erklärender Faktor der Vorhersage. `feature` ist ein TECHNISCHER Tag
 * (Muster {datenpunkt}__{stat} oder die Präfixe drift__, maint__, alarm__) — das
 * UI zeigt ihn NIE roh, sondern paraphrasiert in Hallensprache (lib/prediction/factors.ts).
 * `shap` ist die rohe Gewichts-Zahl der (im UI unbenannten) Faktor-Methode —
 * das UI nutzt nur den Betrag als relative Balkenlänge, nie die Zahl, nie den
 * Methodennamen (Paraphrase-Disziplin §1.3/§4E).
 */
export interface TopFactor {
  feature: string;
  value: number;
  shap: number;
  direction: FactorDirection;
}

/**
 * Ausfallvorhersage (GET/POST /api/v1/reasoners/failure/predict[ions] ·
 * FailurePredictionRead). Liefert NUR einen Punktwert `probability` — KEIN
 * Unsicherheits-Band (das UI erfindet keines, sondern stellt die verfügbare
 * Unsicherheit ehrlich dar; die Ehrlichkeit trägt der Vorbehalt-Block).
 */
export interface FailurePredictionRead {
  id: number;
  machine_id: number;
  reference_time: string; // ISO 8601 (tz-aware)
  horizon_h: number;
  probability: number; // [0, 1] — Punktwert, keine Bandbreite im Vertrag
  decision_threshold: number; // [0, 1]
  decision: RiskDecision;
  top_factors: TopFactor[];
  validation_status: ValidationStatus;
  data_regime: DataRegime;
  model_version: string;
  created_at: string; // ISO 8601
}

/**
 * Werker-Empfehlung über einer Vorhersage (F-REC ·
 * GET/POST /api/v1/reasoners/failure/predictions/{id}/recommendation ·
 * WorkerRecommendationRead). `validation_caveat` ist DETERMINISTISCH vom Backend
 * (validation_caveat_for(), DB-CHECK) — der Vier-Block-Vorbehalt zitiert genau
 * dieses Feld, das Frontend formuliert ihn NIE selbst. probability/decision/
 * horizon_h werden aus der Vorhersage mitgeführt (Invariante I, autoritativ).
 */
export interface WorkerRecommendationRead {
  id: number;
  prediction_id: number;
  machine_id: number;
  recommendation_text: string;
  validation_caveat: string;
  validation_status: ValidationStatus;
  data_regime: DataRegime;
  model_version: string;
  referenced_source_ids: string[];
  horizon_h: number;
  probability: number;
  decision: RiskDecision;
  created_at: string; // ISO 8601
}

/** Request-Body für POST /predict (On-Demand-Auslöser). */
export interface PredictRequestBody {
  machine_id: number;
  reference_time?: string | null;
  lookback_hours?: number | null;
}
