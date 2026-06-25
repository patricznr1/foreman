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

/**
 * Zustand des Eingangs-Live-Streams (Zwilling als Datenquelle, schemas/dashboard.py
 * StreamStatusOut). `active` = der Worker tickt fortlaufend frische Wall-Clock-
 * Readings; `last_reading_at` ist der jüngste Reading-Stempel (Stand) oder null.
 */
export interface StreamStatusOut {
  active: boolean;
  last_reading_at: string | null; // ISO 8601
}

export interface FleetOverviewOut {
  machines: MachineStatusOut[];
  by_status: Record<MachineStatus, number>;
  open_alarm_total: number;
  stream: StreamStatusOut;
}

export interface TrendPointOut {
  bucket: string; // ISO 8601, Minuten-Bucket
  avg: number;
  min: number;
  max: number;
  last: number | null;
}

/** Ein zeitaufgelöster Korridorpunkt des F4-Eigenprofil-Bands (deckt sich mit `points`). */
export interface ProfileBandPointOut {
  bucket: string; // ISO 8601, Minuten-Bucket
  lower: number;
  mid: number;
  upper: number;
}

/**
 * Das zustandsspezifische F4-Eigenprofil-Band (drift_profiles, gegateter Replay).
 * `mid` = gelernter Zustands-Median, `lower`/`upper` = Korridor
 * `median +/- effect_size_k * noise_sigma` (echte Detektor-Bewertungsbasis).
 * `computed_at` = Profil-Stand (kein Live-Wert).
 */
export interface ProfileBandOut {
  computed_at: string; // ISO 8601
  effect_size_k: number;
  points: ProfileBandPointOut[];
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
  /** F4-Eigenprofil-Band; null, wenn kein/zu junges Profil vorliegt (graceful). */
  profile_band: ProfileBandOut | null;
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

// — Stammdaten & Historie (Sektion B — Maschinen-Detail) — gegen den REALEN Code
//   typisiert. Quelle: schemas/resources.py (MachineRead/ComponentRead/DataPointRead/
//   MaintenanceEventRead/WorkerNoteRead), api/routers/{machines,components,data_points,
//   maintenance_events,worker_notes}.py. Personenfelder (`performed_by`/`author`) sind
//   HMAC-Token "v{n}:{hex}" (§8), NIE Klartext — das UI zeigt nur die maskierte Form
//   (#hex6, lib/ui/pii.ts). `worker_notes.text` ist beim Insert bereits NER-maskiert;
//   `maintenance_events.description` ist Sach-/SPS-Text und bewusst NICHT maskiert
//   (dokumentiertes Restrisiko §8).

/** Eine Maschine (GET /api/v1/machines/{id} · MachineRead). `external_id` ist eine
 *  anonymisierte Kennung ohne Personenbezug. */
export interface MachineRead {
  id: number;
  line_id: number | null;
  external_id: string | null;
  label: string;
  machine_class: string | null;
  manufacturer: string | null;
  location: string | null;
  created_at: string; // ISO 8601
}

/** Eine Komponente einer Maschine (GET /api/v1/components?machine_id · ComponentRead). */
export interface ComponentRead {
  id: number;
  machine_id: number;
  label: string;
  component_type: string | null;
  created_at: string; // ISO 8601
}

/** Art eines Datenpunkts (DataPointKind-Literal, schemas/resources.py). */
export type DataPointKind = "analog" | "digital" | "setpoint" | "counter";

/** Protokoll-Herkunft eines Datenpunkts; "simulation" markiert synthetische Tags
 *  (F3), damit Sim-Daten nie als reales Protokoll getarnt werden. */
export type DataPointSource = "opcua" | "modbus" | "mqtt" | "s7" | "simulation";

/** Ein Datenpunkt/Tag einer Maschine (GET /api/v1/data_points?machine_id ·
 *  DataPointRead). `normal_min`/`normal_max` sind das statische Normalband, das auch
 *  der Trend (`/machines/{id}/trend`) als Fläche mitführt. */
export interface DataPointRead {
  id: number;
  machine_id: number;
  component_id: number | null;
  name: string;
  kind: DataPointKind;
  measurement_type: string | null;
  unit: string | null;
  source: DataPointSource | null;
  address: string | null;
  normal_min: number | null;
  normal_max: number | null;
  created_at: string; // ISO 8601
}

/** Ein Wartungs-/Prüfereignis (GET /api/v1/maintenance_events?machine_id ·
 *  MaintenanceEventRead). `performed_by` ist ein HMAC-Token (§8), nie Klartext. */
export interface MaintenanceEventRead {
  id: number;
  machine_id: number;
  component_id: number | null;
  type: string;
  performed_at: string; // ISO 8601
  description: string | null; // Sach-/SPS-Text, NICHT NER-maskiert (§8-Restrisiko)
  performed_by: string | null; // HMAC-Token "v{n}:{hex}", nie Klartext
  created_at: string; // ISO 8601
}

/** Eine Werker-Notiz / ein Schichtbericht (GET /api/v1/worker_notes?machine_id ·
 *  WorkerNoteRead). `text` ist beim Insert bereits NER-maskiert (Personennamen →
 *  [PERSON]); `author` ist ein HMAC-Token (§8). `embedding` wird nie ausgegeben. */
export interface WorkerNoteRead {
  id: number;
  machine_id: number | null;
  shift: string | null;
  text: string; // bereits NER-maskiert (kein Rohtext)
  classification: string | null; // in F2 ungenutzt
  author: string | null; // HMAC-Token "v{n}:{hex}", nie Klartext
  created_at: string; // ISO 8601
}

/**
 * Request-Body für POST /api/v1/worker_notes (eine Notiz erfassen — Sektion J).
 * Gegen den REALEN Vertrag (api/routers/worker_notes.py:WorkerNoteCreate):
 * `text` ist Pflicht (min_length 1); `machine_id`/`shift`/`author` sind optional.
 * Serverseitig: `text` wird VOR dem Insert NER-maskiert, `author` (eine user_id)
 * zu einem HMAC-Token pseudonymisiert (§8) — das Frontend sendet beides im Klartext
 * NUR transient (Offline-Puffer wird nach erfolgreichem Senden gelöscht).
 * `created_at` setzt der Server (tz-aware, nicht vom Client anpassbar).
 *
 * `classification`: ADDITIV mitgesendet (Werker-Kategorie). Das heutige
 * POST-Schema nimmt das Feld NOCH NICHT an und verwirft es still — markierter
 * Backend-Anschlusspunkt (DB-Spalte `worker_notes.classification` existiert,
 * §5/§14.3). Sobald `WorkerNoteCreate` serverseitig das Feld aufnimmt, wirkt es
 * ohne Frontend-Änderung. Kein erfundenes Verhalten: das Frontend erfasst und
 * sendet die Einschätzung vollständig korrekt.
 */
export interface WorkerNoteCreate {
  text: string;
  machine_id?: number | null;
  shift?: string | null;
  author?: string | null;
  classification?: string | null;
}

// — Ereignisketten (Sektion D, F-REC) — gegen den REALEN Code typisiert.
//   Quelle: reasoners/event_chain/schema.py (EventChain/ChainEvent/ChainWindow/
//   SiblingReference/ReasonerExplanationRead/ReasonerExplanationDetailRead),
//   reasoners/event_chain/router.py. KERN: die rekonstruierte Kette + die
//   Schwester-Referenzen werden als EINGEFRORENER Snapshot ausgeliefert (POST
//   /reconstruct, GET /explanations/{id}) — nie bei Re-Fetch neu abgeleitet
//   („Stand X", Studie §3.2). Schwester-Referenzen sind EHRLICH aus realen
//   NEXUS-Recall-Treffern; keine → leere Liste (kein Fake, §21-D).

/** Konfidenz-Stufe der Erzählung (geschlossener Wertebereich) — NIE als Prozent gezeigt. */
export type Confidence = "low" | "medium" | "high";

/** Typ eines Kettenereignisses (formcodiertes Symbol, konsistent mit B). */
export type ChainEventType =
  | "anchor_alarm"
  | "drift_alarm"
  | "prior_alarm"
  | "worker_note"
  | "maintenance";

/** Zeitfenster der Rekonstruktion (tz-aware UTC, geschlossen [start, end]). */
export interface ChainWindow {
  start: string; // ISO 8601
  end: string; // ISO 8601
}

/**
 * Ein einzelnes Ereignis der Kette. `trusted=true` für strukturierte Alarm-/
 * Wartungsdaten; `trusted=false` für Werkernotiz-Freitext (untrusted, im UI als
 * unsicherer markiert). `summary` ist backend-seitig PII-frei bzw. NER-maskiert.
 */
export interface ChainEvent {
  source_id: string; // "alarm:{id}" | "note:{id}" | "maint:{id}"
  event_type: ChainEventType;
  occurred_at: string; // ISO 8601
  machine_id: number | null;
  summary: string;
  trusted: boolean;
}

/** Die rekonstruierte, zeitlich geordnete Ereigniskette um einen Anker-Alarm. */
export interface EventChain {
  anchor_alarm_id: number;
  machine_id: number | null;
  window: ChainWindow;
  events: ChainEvent[];
}

/**
 * Eine ehrliche Schwester-Referenz aus einem realen Recall-Treffer (§21-D).
 * Strukturierte Ziele (`machine_id`/`machine_class`/`explanation_id`) sind NUR
 * gesetzt, wenn real auflösbar — sonst null (kein erfundenes Geschwister).
 * `similarity_basis` benennt PII-frei, woran die Ähnlichkeit hängt; `excerpt` ist
 * der backend-sanitisierte Kurz-Auszug (untrusted, reine Anzeige).
 */
export interface SiblingReference {
  recall_ref: string | null;
  machine_id: number | null;
  machine_class: string | null;
  explanation_id: number | null;
  similarity_basis: string;
  excerpt: string;
}

/**
 * Listen-/Kopf-Sicht einer gespeicherten Erklärung (GET /explanations).
 * `confidence` ist die verbale Stufe (NIE Prozent); `is_hypothesis`/
 * `flagged_unsupported` tragen die Vorbehalt-/Ehrlichkeits-Haltung.
 */
export interface ReasonerExplanationRead {
  id: number;
  anchor_alarm_id: number;
  machine_id: number | null;
  reasoner: string;
  narrative: string;
  referenced_source_ids: string[];
  flagged_unsupported: string[];
  is_hypothesis: boolean;
  confidence: Confidence;
  grounded: boolean | null;
  recall_used: boolean;
  created_at: string; // ISO 8601
}

/**
 * Detail-Sicht (POST /reconstruct, GET /explanations/{id}): Superset der Liste
 * plus eingefrorene Kette (`chain`) + Schwester-Referenzen (`siblings`). `chain`
 * ist null für Datensätze vor der Snapshot-Migration (graceful); `siblings` ist
 * dann leer.
 */
export interface ReasonerExplanationDetailRead extends ReasonerExplanationRead {
  chain: EventChain | null;
  siblings: SiblingReference[];
}

/** Request-Body für POST /reconstruct (On-Demand-Auslöser; Anker IST ein Alarm). */
export interface ReconstructRequestBody {
  anchor_alarm_id: number;
  lookback_hours?: number | null;
}
