# GROUND_TRUTH — FOREMAN

> **Single Source of Truth.** Dieses Dokument beschreibt, was *gilt* — Schema, Routen, Stack, Konventionen. Bei Widerspruch zwischen Code und diesem Dokument gewinnt zunächst dieses Dokument; danach wird eines von beiden korrigiert. Stand-Datum bei jeder Änderung aktualisieren.

**Stand:** 2026-06-16 · **Status:** F7 — MCP-Schnittstelle (FOREMAN als offener Knoten, **zweiter Differenzierungs-Pfeiler „Plattform statt App"**). Neue Schicht `src/foreman/mcp/`: ein **read-only** Model-Context-Protocol-Server (Anthropic SDK / FastMCP, Streamable HTTP), der die aggregierten Reasoner-Erkenntnisse als **11 maschinenlesbare Tools** an Drittsysteme (Simulation/ERP/Energiemanagement) reicht. Drei Invarianten, strukturell verankert: **(I) read-only** — keine Aktorik, kein Reasoner-/LLM-Trigger über MCP (MCP-eigene Read-Schicht `reads.py`, ausschließlich SELECT); **(II) AI-Act-Transparenz** an jedem KI-Output (Art. 50(2): `ai_generated`/`generated_by`/`requires_human_review`/`model_version` + bei Vorhersage/Empfehlung `validation_status`/`data_regime`/`validation_caveat`) — ein gemeinsamer Wrapper, dessen Validator einen unehrlichen Umschlag nicht zulässt; **(III) IP-Wording** — kein internes Vokabular in Tool-Namen/-Beschreibungen/-Schemata (Hidden-Term-Scan als Akzeptanzkriterium). Eigener `FOREMAN_MCP_`-Token (getrennt vom Plattform-JWT, Fail-Closed), PII nur pseudonymisiert/maskiert (Token nie aufgelöst), `foreman_mcp_*`-Metriken, eigenständige ASGI-App (eigener Port, eigene `/health`/`/metrics`). **Erfüllt zugleich AI-Act-Maßnahme §10.5(2) — Transparenz-Flag MCP: „gebaut".** Vertrag: **§17**.

*Vorgänger-Status F-REC — LLM-Werker-Empfehlung (Erklär-Layer über F-PRED, **zweiter Konsument des `LLMGateway`** nach F6): aus einer `FailurePrediction` + SHAP-Faktoren (`trusted=True`) + NEXUS-Recall (`trusted=False`, best-effort) eine deutsche Werker-Empfehlung über `gateway.complete(task=explanation)`. Zwei strukturell erzwungene Invarianten: (I) Zahlen autoritativ vom Modell — der numerische Post-Check **rejectet** (nicht: flaggt) jede unbelegte Zahl, keine Persistenz; (II) deterministischer Sim-Vorbehalt — `validation_caveat` aus `validation_caveat_for(...)`, nie aus dem LLM. Persistenz `failure_recommendations` (Migration `0007`, FK auf `failure_predictions`) + Dual-Write. Red-Team scharf über den Recall-Pfad ✅. Vertrag: §16.5.*

*Vorgänger-Status F-PRED — Ausfallvorhersage-Reasoner (Reasoner #3), **ehrlich deklarierter Methoden-Demonstrator**: klassisches ML (LightGBM `LGBMClassifier`, binär) + SHAP-`TreeExplainer`-Faktor-Attribution, reine/netzfreie Feature-Extraktion ohne Zeit-Leakage (`readings_1m`-Aggregate + Drift-Output als Feature + Wartung/Alarm), Trainingsdatensatz aus den Szenarien (Label aus `ground_truth.failure` + Horizont, **lauf-disjunkter** Split), reproduzierbares Offline-Training (CLI, Seed), Inferenz lädt das Artefakt → persistierte `FailurePrediction`, on-demand-Routen, `foreman_failure_*`-Metriken. **Strukturelle Ehrlichkeit (Kern):** `validation_status=simulation_only` ist Pflichtfeld an jeder Vorhersage, `data_regime=simulation` Label auf allen Kennzahlen — der prädiktive Wert setzt reale Run-to-failure-Daten voraus (über den SPS-Programm-Kanal grundsätzlich nicht verfügbar). Vertrag: **§16** + Model Card `docs/models/failure_prediction_model_card.md`. Baut auf F2 + F3 + F4 (Drift-Output als Feature) + F-LLM (Gateway, Zahlen nie aus dem LLM) auf.*

*Vorgänger-Status F-SEM — Semantische Notiz-Suche (Querfunktion, kein neuer Reasoner): eigene dünne `EmbeddingProvider`-Abstraktion (analog `LLMGateway`, lokal-first Ollama `bge-m3` + sentence-transformers-Alternative, L2-normierte 1024-Vektoren), Embedding beim Insert (best-effort) + idempotenter Backfill, HNSW-Index (Migration `0004`) + reine DB-Suche + read-only `GET /api/v1/worker_notes/search`, und die additive, best-effort F6-Anbindung. Vertrag: **§15**.*

*Vorgänger-Status F6 — Ereignisketten-Reasoner (erster LLM-Freitext-Reasoner + erster Konsument des `LLMGateway`): Ketten-Konstruktion (rein) + NEXUS-Recall ähnlicher Vorfälle (best-effort) + Grounding-Quellen (`worker_notes` untrusted) → gegroundete deutsche Erzählung über `gateway.complete(task=synthesis)`, Output-Guard (`ReasonerExplanation`), Persistenz `reasoner_explanations` + `semantic_event`-Dual-Write, on-demand-Routen, Event-Ketten-`/metrics`. **Red-Team scharf am ersten Freitext-Reasoner ✅** (Vertrag §14).*

---

## 1. Projekt-Identität

- **Name:** FOREMAN
- **Tagline:** Production Intelligence with Memory
- **Zweck:** Reasoning-Plattform mit Langzeitgedächtnis für industrielle Produktionsumgebungen.
- **Kontext:** MSIT AI-Track Capstone.

---

## 2. Architektur (verbindlich)

Drei Schichten:

1. **Industrieumgebung** — Datenquellen: SPS/OPC UA, MQTT, Modbus, Logs, Wartungshistorie.
2. **FOREMAN-Plattform** — Ingestion + vier Reasoner + Modell-Gateway.
3. **Output-Kanäle** — Werker-Dashboard (F5, geplant) + **MCP-Schnittstelle (F7 ✅, read-only — FOREMAN als offener Knoten, §17)**.

**Gedächtnis-Substrat:** externer Dienst hinter HTTP-API. Wird wie eine Datenbank konsumiert. **Kein Substrat-Code in diesem Repo.**

### Die vier Reasoner

| # | Reasoner | Substrat-Fähigkeit (angebunden) |
|---|---|---|
| 1 | Ereignisketten-Rekonstruktion | zeitgefilterter Recall + Reasoning |
| 2 | Drift-Erkennung | Drift-/Stabilitäts-Überwachung |
| 3 | Ausfallvorhersage | Mustererkennung über konsolidiertem Speicher |
| 4 | Wartungszyklen-Analyse | kausale Auswertung (read-only) |

**Bau-Status:** Reasoner #1 (Ereignisketten, F6 ✅), #2 (Drift, F4 ✅), **#3 (Ausfallvorhersage, F-PRED ✅** — ehrlich deklarierter Methoden-Demonstrator auf Simulationsdaten, §16). **#4 (Wartungszyklen) folgt — datenabhängig** (echte Wartungshistorie).

**Belastungsdaten — kein Reasoner, sondern MCP-Datenfähigkeit.** FOREMAN führt **keine** eigene Belastungs-Simulation durch: eine echte Lastsimulation braucht Parameter außerhalb von FOREMANs Beobachtungsgrenze (Taktung der Teilespender, Materialverhalten von Werkzeug/Produkt, Umgebung), die die Plattform nie sieht — selbst zu simulieren hieße, Wissen über die Beobachtungsgrenze hinaus vorzutäuschen (dieselbe Linie wie Sim-Vorbehalt §16, „nur Belegbares", HITL ohne Aktorik). Stattdessen exponiert FOREMAN die **beobachteten** Lastdaten (historische Lastprofile, beobachtete Maximalwerte + ihre Folgen) read-only über die MCP-Schicht (§17); die eigentliche Simulation fährt **extern** bei einem Simulations-Konsumenten (externe Simulationssoftware als MCP-Konsument — in der Systemtopologie ehrlich als [VISION]-Drittsystem geführt, §22.2). Diese Lastprofil-Datenfähigkeit ist **noch nicht gebaut** (kein eigenes MCP-Tool neben `get_readings`, §17) und wird, wenn überhaupt, in der MCP-Schicht ergänzt — **nicht** als interner Reasoner.

---

## 3. Tech-Stack (verbindlich)

- **Backend:** Python 3.12, FastAPI 0.115+, async SQLAlchemy 2.0, Pydantic v2
- **DB:** PostgreSQL + TimescaleDB + Vektor-Suche
- **Gateway:** eigene dünne `LLMGateway`-Abstraktion (`src/foreman/llm/`, F-LLM); LiteLLM ist ausschließlich Implementierungsdetail dahinter (`backends.py`). Lokal-first Qwen3 (Ollama) + Anthropic Cloud-Fallback, vier Priority-Modi. Reasoner sehen nur `LLMGateway`/`GatewayResponse`/`Task`/Fehlerhierarchie — nie einen LiteLLM-Typ. vLLM-Production-Pfad bleibt durch die Backend-Config offen. Vertrag: **§13**.
- **Embeddings:** eigene dünne `EmbeddingProvider`-Abstraktion (`src/foreman/embeddings/`, F-SEM) — **parallel** zum Gateway, NICHT in den `LLMGateway` gequetscht (Completion ≠ Embedding). Lokal-first über Ollama (`bge-m3`, Default) + sentence-transformers-Alternative hinter derselben Schnittstelle; L2-normierte Vektoren, Dimension 1024 erzwungen (passt auf `vector(1024)`). Aufrufer (Ingestion, Suche, Reasoner) sehen nur `EmbeddingProvider`/`Vector`/`EmbeddingSettings`/Fehlerhierarchie — nie einen Backend-/Library-Typ. Vertrag: **§15**.
- **Frontend:** Next.js 15 (App Router), React 19, TypeScript strict, Tailwind CSS 4, Vitest + Testing Library; **bespoke token-getriebenes SVG statt Charting-Lib** (kein shadcn/ui, kein Recharts) — Details §21
- **Industrie:** asyncua, paho-mqtt, pymodbus
- **Integration:** MCP SDK
- **Betrieb:** Docker Compose

---

## 4. API-Konventionen

- Basis-Pfad: `/api/v1/`
- Ressourcen-Stil: `/api/v1/<resource>` (Plural, snake_case in der DB)
- Health-Check: `GET /health`
- Auth-Middleware auf allem **außer** `/auth/login`, `/auth/register`, `/health` sowie der OpenAPI-Doku (`/`, `/docs`, `/redoc`, `/openapi.json`) und CORS-Preflight (`OPTIONS`).

### Routen (F2-Skeleton)

- `GET /health`
- `POST /auth/register`, `POST /auth/login` (JWT-Ausgabe)
- `GET /api/v1/me` — Identität + Rolle + Per-User-Scope (`assigned_line_ids`/`assigned_machine_ids`) des eingeloggten Nutzers. Auth-pflichtig (401 ohne Token; nicht in der Open-Path-Whitelist). **Read-only** — das Frontend spiegelt damit die Server-Autorisierung (Rollenmatrix 3.1, §20.4), ersetzt sie nicht. **Keine Aktorik**; keine PII über die eigene Identität hinaus (kein `password_hash`). Frontend-Enabler für das Rollen-Routing (F5-Frontend).
- `GET /api/v1/ws-ticket` — **kurzlebiges, WS-scoped Ticket** (`aud="ws"`, 60 s) für den `?token=`-Query von `/api/v1/ws`. Auth-pflichtig (401 ohne Token). **Read-only, keine Aktorik.** Scope-begrenzt: das Ticket ist auf HTTP-Routen NICHT gültig (`decode_access_token` lehnt `aud`-tragende Tokens ab) — so muss das Frontend nicht das volle Session-JWT an Browser-JS ausliefern (Security-Härtung). Krypto: `core/security.create_ws_ticket`/`decode_ws_token`.
- CRUD: `/api/v1/lines`, `/api/v1/machines`, `/api/v1/components`, `/api/v1/data_points`, `/api/v1/production_runs`, `/api/v1/maintenance_events`, `/api/v1/worker_notes`, `/api/v1/alarms`
- `POST /api/v1/readings` — Batch-Aufnahme von Messwerten (HTTP). Nutzt seit F3 denselben geteilten COPY-Schreibweg wie der Ingestion-Service (`ingestion/service.py:copy_readings`) — siehe §12.
- `GET /api/v1/worker_notes/search` — **semantische Notiz-Suche** (F-SEM, read-only, Auth-pflichtig). Query-Parameter `q` (Freitext, wird eingebettet), `machine_id` (optionaler Filter), `k` (1–50, Default 5). Liefert die ähnlichsten Notizen (Cosine, ohne Vektor in der Antwort). **Vor** dem `worker_notes`-CRUD-Router gemountet, damit `/search` nicht von `/{note_id}` gefangen wird. 503 bei Embedding-Backend-Ausfall (ehrlich, nicht best-effort). Vertrag: §15.
- `GET /api/v1/substrate/smoke` — Substrat-Round-Trip (siehe §9)

### Reasoner-Routen (Drift, ab F4)

- `GET /api/v1/reasoners/drift/alarms` — Auflistung der Drift-Warnungen (`code=DRIFT`), optional gefiltert nach `machine_id` und `acknowledged`.
- `POST /api/v1/reasoners/drift/alarms/{alarm_id}/acknowledge` — **HITL-Quittierung** einer Drift-Warnung. Auth-pflichtig; `acknowledged_by` wird als HMAC-Token über die `users.id` abgelegt (§8). **Keine Aktorik** — setzt nur den Quittierungs-Status.
- `GET /metrics` — Prometheus-Format (§11.2), Root-Ebene, in der Auth-Whitelist (Scraper hat kein JWT). Request-/Latenz-Zähler je Reasoner + Drift-Kennzahlen (Detektionsverzug, Fehlalarm-Zähler).

### Reasoner-Routen (Ereignisketten, ab F6)

- `POST /api/v1/reasoners/event_chain/reconstruct` — **on-demand** Rekonstruktion der Ereigniskette um einen Anker-Alarm. Body: `{ "anchor_alarm_id": int, "lookback_hours": int|null }`. Liefert die persistierte, gegroundete `ReasonerExplanation` (201). Auth-pflichtig (LLM-Kostenschutz). **Kein automatischer LLM-Call pro Drift-Alarm** — der alarm-getriebene Hook bleibt bewusst offen/unverdrahtet (kostenkontrollierter LLM-Einsatz). **Keine Aktorik** — der Reasoner erklärt, schaltet nichts. 404, wenn der Anker nicht existiert.
- `GET /api/v1/reasoners/event_chain/explanations` — Auflistung gespeicherter Erklärungen (jüngste zuerst), optional gefiltert nach `machine_id` (`limit`/`offset`).
- `GET /api/v1/reasoners/event_chain/explanations/{explanation_id}` — eine einzelne gespeicherte Erklärung; 404, wenn nicht vorhanden.

### Reasoner-Routen (Ausfallvorhersage, ab F-PRED)

- `POST /api/v1/reasoners/failure/predict` — **on-demand** Ausfallvorhersage für eine Maschine. Body: `{ "machine_id": int, "reference_time": datetime|null, "lookback_hours": int|null }` (`reference_time` null → jetzt/UTC; `lookback_hours` null → Artefakt-Default). Liefert die persistierte `FailurePrediction` (201) **inkl. Sim-Vorbehalt** (`validation_status=simulation_only`, `data_regime`, `model_version`). Auth-pflichtig. **Kein Auto-Predict** (on-demand, Konsistenz mit F6). **Keine Aktorik.** 404, wenn die Maschine nicht existiert. Der Horizont kommt aus dem Artefakt, nicht aus dem Request.
- `GET /api/v1/reasoners/failure/predictions` — Auflistung persistierter Vorhersagen (jüngste zuerst), optional gefiltert nach `machine_id` (`limit`/`offset`).
- `GET /api/v1/reasoners/failure/predictions/{prediction_id}` — eine einzelne Vorhersage; 404, wenn nicht vorhanden.

### Reasoner-Routen (LLM-Werker-Empfehlung, ab F-REC)

- `POST /api/v1/reasoners/failure/predictions/{prediction_id}/recommendation` — **on-demand** LLM-Werker-Empfehlung zu einer bestehenden Vorhersage. Liefert die persistierte `WorkerRecommendation` (201) **inkl. deterministischem Sim-Vorbehalt** (`validation_caveat`, `validation_status`, `data_regime`, `model_version`) + den aus der Vorhersage geerbten autoritativen Zahlen (`probability`/`horizon_h`/`decision`). Auth-pflichtig (LLM-Kostenschutz). **Kein Auto-LLM** (on-demand, Konsistenz mit F6). **Keine Aktorik** — die Empfehlung erklärt, schaltet nichts. **404**, wenn die Vorhersage nicht existiert. **422**, wenn die erzeugte Empfehlung den Grounding-/Vorbehalts-Guard nicht besteht (unbelegte Zahl — Invariante I — bzw. Umdeutung des Sim-Vorbehalts — Invariante II); in dem Fall wird **nichts** persistiert. *(Unter dem `predictions/{id}`-Ressourcen-Präfix — konsistent mit F-PRED `/predictions/{id}` und F6 `/explanations/{id}`.)*
- `GET /api/v1/reasoners/failure/predictions/{prediction_id}/recommendation` — die jüngste persistierte Empfehlung zu einer Vorhersage; 404, wenn keine vorhanden (ohne POST existiert keine — kein Auto-LLM).

*(Routen-Namespace `reasoners/<reasoner>/…` analog zu `reasoners/drift`. Weitere Reasoner-Routen folgen je Phase.)*

### MCP-Schnittstelle (read-only, ab F7)

Eigenständiger Model-Context-Protocol-Server (Anthropic SDK / FastMCP, **Streamable HTTP**, Default-Port `8081`) — **getrennt** von der Plattform-FastAPI-App (eigener Token, eigener Port). Remote erreichbar für Drittsysteme; **kein** Tool schaltet etwas, **keines** löst eine Reasoner-Berechnung aus. Vollständiger Vertrag: **§17**.

- **Transport:** `POST/GET /mcp` (Streamable HTTP). Auth-pflichtig über den `FOREMAN_MCP_`-Token (Bearer); fehlendes/ungültiges Credential → 401, Abruf-Last-Bremse → 429.
- **Offene Pfade (kein Token):** `GET /health`, `GET /metrics` (Prometheus, enthält `foreman_mcp_*`).
- **Read-only Tools (11):** `list_machines`, `get_machine`, `get_drift_status`, `get_alarms(machine_id?, since?, severity?)`, `list_failure_predictions(machine_id?)`, `get_failure_prediction(prediction_id)`, `get_worker_recommendation(prediction_id)`, `list_event_chains(machine_id?)`, `get_event_chain(explanation_id)`, `search_notes(query, machine_id?, k?)`, `get_readings(machine_id, datapoint, hours?)`. Alle mit `readOnlyHint=True`.
- **Transparenz:** KI-stämmige Ausgaben (Vorhersage, Empfehlung, Ereignisketten-Erklärung) tragen die Art.-50(2)-Flags + (Vorhersage/Empfehlung) den Sim-Vorbehalt; Stammdaten/Readings/Alarme **nicht** als KI gekennzeichnet.

### Dashboard- & Live-Push-Routen (F5)

In die Plattform-FastAPI-App integriert (nicht der MCP-Server). Vollständiger Vertrag: **§20**.

- `GET /api/v1/overview` — Flotten-Lagebild (Statusleiste/Cockpit): je Maschine komponierter FCSM-Status + offene Alarme nach Severity + jüngster offener Alarm, plus Status-Rollup. Auth-pflichtig; **scope-korrekt + autorisiert** wie das WS-`overview`-Thema — nur `manager`/`shift_lead` (sonst **403**), `shift_lead` auf seine Linien gefiltert.
- `GET /api/v1/machines/{machine_id}/trend?datapoint=<name>&hours=<1–168>` — aggregierter `readings_1m`-Trend eines Datenpunkts + statisches Normalband (`normal_min`/`normal_max`). Auth-pflichtig; **gleiche Maschinen-Scope-Autorisierung** wie das WS-`machine`-Thema (**403** außerhalb des Scopes). **404**, wenn der Datenpunkt an der Maschine nicht existiert.
- `WS /api/v1/ws?token=<jwt>` — **EIN** gemultiplexter WebSocket-Kanal mit Themen-Abos. Auth über Query-Token (die AuthMiddleware lässt WS-Scope durch → manuelle Auth, Close-Code 4401). Client-Nachrichten `{action: subscribe|unsubscribe, topic}`; jeder `subscribe` wird **autorisiert** (default-deny), bei Erfolg sofort ein Snapshot, danach Live-Deltas. Themen: `overview`, `machine:{id}`, `trend:{data_point_id}`.

### Audit- & Plattform-Routen (Sektion I, ab I-Backend)

In die Plattform-FastAPI-App integriert. Vollständiger Vertrag: **§22**.

- `GET /api/v1/audit` — unveränderlicher Audit-Trail (jüngste zuerst), gefiltert nach `action_type`/`target_kind`/`target_id`/`actor`/`machine_id`/`since`/`until`, paginiert (`limit` 1–1000, `offset`). **Nur `manager`/Admin** (Schichtleiter/Techniker/Werker → **403**). `actor` bleibt pseudonym (HMAC-Token).
- `GET /api/v1/topology` — ehrlich abgeleitete Systemtopologie (Eingänge aus `data_points.source` + jüngster `readings`-Aktivität, Gedächtnis-Substrat-Health, F7-MCP-Grenze). `manager` voll; `shift_lead` **nur Verbindungsstatus** (kein Audit-Bezug); `worker`/`technician` → **403**. Optionale Query: `probe` (Substrat live proben, schreibt Smoke-Marker), `fresh_within_minutes`.

---

## 5. Datenbank-Schema

Tabellen: `snake_case`. Hierarchie: **Linie → Maschine → Komponente → Datenpunkt**. Ein Datenpunkt hängt immer an einer Maschine und optional zusätzlich an einer Komponente. Produktionskontext liegt auf **Linien-Ebene** (Welt A: ein Auftrag läuft als Ganzes über die Straße).

Vier Datenkategorien aus der SPS, sauber getrennt: analoge Messwerte und digitale I/O als Zeitreihe (`readings`), Fehlermeldungen/Nothalt als Ereignisse (`alarms`), Produktionskontext über Zeit (`production_runs`).

**`lines`** — Fertigungsstraßen
- `id` PK · `label` · `location` · `created_at`

**`machines`** — Maschinen
- `id` PK · `line_id` FK→lines (nullable, für Einzelmaschinen) · `external_id` (anonymisiert) · `label` · `machine_class` · `manufacturer` · `location` · `created_at`

**`components`** — Komponenten einer Maschine
- `id` PK · `machine_id` FK→machines · `label` · `component_type` (spindle/drive/bearing/motor/axis/…) · `created_at`

**`data_points`** — Datenpunkte / Tags (ersetzt „sensors")
- `id` PK · `machine_id` FK→machines (immer) · `component_id` FK→components (nullable) · `name` · `kind` (analog/digital/setpoint/counter) · `measurement_type` (voltage/current/dc_bus/temperature/speed/frequency/torque/force/signal/null) · `unit` (V/A/°C/rpm/Hz/Nm/N/kN/bool/…) · `source` (opcua/modbus/mqtt/s7/**simulation**) · `address` (Node-ID/Register) · `normal_min` · `normal_max` · `created_at`
  - `source = simulation` (F3): synthetische Datenpunkte des Simulations-Adapters — bewusst eigener Wert, damit Sim-Daten nie als reales Protokoll getarnt werden. Validierung im API-Schema (`DataPointSource`-Literal). **Kein DB-CHECK-Constraint** auf `source` vorhanden → **keine Migration** nötig (nur Type-/Doku-Nachzug).

**`readings`** — TimescaleDB-Hypertable (analoge Messwerte + digitale I/O als 0/1)
- `time` timestamptz · `data_point_id` FK→data_points · `value` double · `quality` smallint (nullable) · PK (`data_point_id`, `time`) · Hypertable auf `time`

**`alarms`** — Fehlermeldungen + Nothalt
- `id` PK · `machine_id` FK→machines · `component_id` FK (nullable) · `data_point_id` FK (nullable) · `code` · `message` · `severity` (info/warning/alarm/critical/emergency) · `category` (process/safety/hardware/electrical/…) · `raised_at` · `cleared_at` (nullable) · `acknowledged_at` (nullable) · `acknowledged_by` (pseudonymisiert: HMAC-Token über `users.id`, nullable; **Nachweis-Bezug**, auditiert re-identifizierbar für HITL/Behörde) · `created_at`
- Nothalt = `category=safety`, `severity=emergency`.

**`production_runs`** — Produktionskontext (Linien-Ebene)
- `id` PK · `line_id` FK→lines · `product_code` · `order_id` (nullable) · `batch` (nullable) · `started_at` · `ended_at` (nullable) · `created_at`

**`maintenance_events`**
- `id` PK · `machine_id` FK · `component_id` FK (nullable) · `type` · `performed_at` · `description` · `performed_by` (pseudonymisiert: HMAC-Token über `users.id`; **Nachweis-Bezug**, auditiert re-identifizierbar) · `created_at`

**`worker_notes`** — Schichtberichte
- `id` PK · `machine_id` FK (nullable) · `shift` · `text` · `classification` (nullable, **weiterhin ungenutzt** — späterer Encoder, nicht F-SEM) · `embedding` (`vector(1024)`, nullable; **ab F-SEM für die semantische Notiz-Suche genutzt** — beim Insert best-effort gefüllt, Backfill für Altbestand, HNSW-Index aus Migration `0004`) · `author` (pseudonymisiert: HMAC-Token über `users.id`) · `created_at`
- `text` (Freitext): Personennamen werden **vor dem Insert** per NER maskiert (Restrisiko bleibt; nie als anonym deklariert). **Eingebettet wird der NER-maskierte Text** (kein Rohtext; §8/§15).

**`users`** — Auth
- `id` PK · `email` (unique) · `password_hash` · `role` · `assigned_line_ids` (`bigint[]`, Default `{}`) · `assigned_machine_ids` (`bigint[]`, Default `{}`) · `created_at`
- **Rollen-Vokabular (F5, englische IDs):** `worker` (Default), `shift_lead`, `technician`, `manager` — UI-Labels deutsch (Werker/Schichtleiter/Techniker/Manager). `assigned_*` sind die Scope-Quelle der WS-/HTTP-Abo-Autorisierung (§20): `worker` → seine Maschinen, `shift_lead` → seine Linien; `manager`/`technician` unrestricted. Leeres Array = kein Scope (default-deny).

**`audit_logs`** — unveränderlicher Audit-Trail (Sektion I) + AI-Act-/Art.-50-Nachweis-Beleg
- `id` PK · `user_id` FK (nullable, **Legacy-Skelett — vom Audit-Schreibpfad NICHT befüllt**) · `action` (Legacy-NOT-NULL, spiegelt `action_type`) · `target` (Legacy, menschenlesbarer Ziel-Spiegel) · `actor` (**pseudonym: HMAC-Token, nie Klartext** — Werker-ID bzw. konstantes MCP-Consumer-Label) · `actor_role` · `action_type` (CHECK `IN (hitl_acknowledge, mcp_retrieval)`, NULL-tolerant, erweiterbar) · `target_kind` · `target_id` · `machine_id` (für den Filter, **ohne FK** — der Trail überlebt eine Maschinen-Löschung) · `origin` (CHECK `IN (dashboard, mcp, system)`) · `detail` jsonb (PII-frei: Tool/IDs/Entscheidung) · `occurred_at` (tz-aware, server_default `now()`) · `created_at`
- **Unveränderlichkeit (Defense-in-Depth, §22):** ein DB-Trigger weist `UPDATE`/`DELETE` auf `audit_logs` ab (append-only; Migration `0010`). `user_id` bleibt erhalten, wird aber nicht befüllt — der namentliche Nachweis lebt im QM-System (System of Record), nicht in FOREMAN (analog `acknowledged_by`). Zwei reale Schreibpfade: HITL-Quittierung (`origin=dashboard`, atomar mit der Quittier-Transaktion) und MCP-Abruf (`origin=mcp`, separater Sink/Commit — die MCP-Read-Invariante bleibt intakt).

**`semantic_events`** — Spiegel der Dual-Writes ans Substrat
- `id` PK · `machine_id` FK (nullable) · `event_type` · `payload` jsonb · `substrate_ref` (nullable) · `created_at`

**`reasoner_explanations`** — persistierte Reasoner-Erklärungen (ab F6, reasoner-übergreifend)
- `id` PK · `anchor_alarm_id` FK→alarms · `machine_id` FK (nullable) · `reasoner` (Default `event_chain`) · `narrative` (Erzähltext, output-sanitisiert) · `referenced_source_ids` jsonb (whitelisted Zitate) · `flagged_unsupported` jsonb (erfundene Quellen + unbelegte Zahlen) · `is_hypothesis` · `confidence` (low/medium/high) · `grounded` (nullable, Gateway-Grounding-Befund) · `recall_used` · `created_at`
- Die Reasoner-Erklärung ist ein **diskretes Ereignis** → wird zusätzlich als `semantic_event` (`event_type=event_chain_reconstructed`) ans Substrat gespiegelt (§12.4). Indizes: `ix_reasoner_explanations_anchor`, `ix_reasoner_explanations_machine_created`.

**`failure_predictions`** — persistierte Ausfallvorhersagen (ab F-PRED)
- `id` PK · `machine_id` FK→machines · `reference_time` (Bezugszeitpunkt, tz-aware) · `horizon_h` (Vorhersagehorizont in Stunden) · `probability` (Ausfallwahrscheinlichkeit) · `decision_threshold` (kostensensitiv) · `decision` (`elevated_risk`/`normal`) · `validation_status` (**Pflicht, einziger Wert `simulation_only`** — §16) · `data_regime` (`simulation`) · `model_version` · `top_factors` jsonb (SHAP-Faktoren `{feature, value, shap, direction}`) · `created_at`
- **Strukturelle Ehrlichkeit (§16):** `validation_status`/`data_regime`/`model_version` werden mitgeführt — der Sim-Vorbehalt überlebt die Persistenz und ist nicht abstreifbar. On-demand erzeugt; **keine Aktorik.** Index: `ix_failure_predictions_machine_created`.

**`failure_recommendations`** — persistierte LLM-Werker-Empfehlungen (ab F-REC)
- `id` PK · `prediction_id` FK→failure_predictions · `machine_id` FK→machines · `recommendation_text` (geguardeter, output-sanitisierter LLM-Output) · `validation_caveat` (**deterministischer Sim-Vorbehalt, NICHT LLM-generiert** — Invariante II) · `validation_status` (**Pflicht, `simulation_only`**) · `data_regime` (`simulation`) · `model_version` · `referenced_source_ids` jsonb (whitelisted Zitate `pred:`/`factor:`/`recall:`) · `horizon_h` · `probability` · `decision` (autoritativ aus der Vorhersage — Invariante I, nie aus dem LLM) · `created_at`
- **Defense-in-Depth (§16.1, analog `failure_predictions`):** DB-CHECK-Constraints erzwingen `validation_status='simulation_only'`, `data_regime='simulation'`, `decision IN ('elevated_risk','normal')` und — als zweite Linie für Invariante II — `validation_caveat` **exakt = dem deterministischen Sim-Vorbehalt** (jede Umdeutung wird an der Persistenzgrenze abgewiesen; die App-Garantie bleibt der Schema-Validator). Zusätzlich koppelt ein **Composite-FK** `(prediction_id, machine_id)` → `failure_predictions(id, machine_id)` die `machine_id` konsistent an die referenzierte Vorhersage (kein inkonsistenter Datensatz möglich; verlangt `UNIQUE(id, machine_id)` auf `failure_predictions`). Die Empfehlung ist ein **diskretes Ereignis** → zusätzlich als `semantic_event` (`event_type=failure_recommendation`, **`data_regime=simulation` im Payload**) ans Substrat gespiegelt (§12.4), damit das Gedächtnis die Sim-Empfehlung nie als reale Prognose ablegt. Indizes: `ix_failure_recommendations_prediction`, `ix_failure_recommendations_machine_created`.

*(Migrationen via Alembic. Jede Migration hier kurz vermerken.)*

- **`0001_initial_schema`** — alle Tabellen aus §5 mit PK-/FK-Constraints + Lese-Indizes (`ix_data_points_machine`, `ix_alarms_machine_raised`, `ix_worker_notes_machine`). `readings` entsteht als gewöhnliche Tabelle (PK `(data_point_id, time)`).
- **`0002_timescale_setup`** — aktiviert die `vector`-Extension und ergänzt `worker_notes.embedding vector(1024)` (deshalb liegt die Embedding-Spalte in 0002, nicht 0001); aktiviert `timescaledb`; macht `readings` zur Hypertable (1-Tages-Chunks); Columnstore (`segmentby=data_point_id`, `orderby=time DESC`, ab 7 Tagen); Continuous Aggregates `readings_1m`→`_1h`→`_1d` (1m real-time) mit Refresh-Policies; Retention 90 d / 1 a / 5 a / ∞. Quelle: `docs/research/timescaledb-tuning-readings.md` §3–§4.
- **`0003_reasoner_explanations`** — legt die Tabelle `reasoner_explanations` an (F6) mit FK auf `alarms`/`machines`, JSONB-Spalten für referenzierte/geflaggte Quellen und den Lese-Indizes `ix_reasoner_explanations_anchor` + `ix_reasoner_explanations_machine_created`.
- **`0004_worker_notes_hnsw`** — HNSW-Index `ix_worker_notes_embedding_hnsw` auf `worker_notes.embedding` (F-SEM, `vector_cosine_ops`, `m=16`, `ef_construction=200`; Quelle: `docs/research/vektor-suche-pgvector.md`). Pflicht ist die pgvector-**Extension** ≥ 0.8.2 im Postgres-Image (CVE-2026-3172 bei parallelen HNSW-Builds) — eine DB-/Deployment-Anforderung, NICHT der Python-Adapter `pgvector` im `pyproject` (der nur das SQLAlchemy-Mapping liefert). Im Betrieb mit großem Bestand per `CREATE INDEX CONCURRENTLY` (Doku-Hinweis in der Migration); in der Migration transaktional (MVP-Bestand unkritisch).
- **`0005_failure_predictions`** — legt die Tabelle `failure_predictions` an (F-PRED) mit FK auf `machines`, JSONB-Spalte für die SHAP-Top-Faktoren, den Pflicht-Vorbehalt-Spalten (`validation_status`/`data_regime`/`model_version`) und dem Lese-Index `ix_failure_predictions_machine_created`.
- **`0006_failure_predictions_checks`** — härtet `failure_predictions` mit DB-CHECK-Constraints (Sim-Vorbehalt + gültige Entscheidung an der Persistenzgrenze, §16.1).
- **`0007_failure_recommendations`** — legt die Tabelle `failure_recommendations` an (F-REC) mit FK auf `failure_predictions` (+ `machines`), JSONB-Spalte für die referenzierten Quellen, den Vorbehalt-/Caveat-Spalten und den geerbten autoritativen Zahlen; CHECK-Constraints (Sim-Vorbehalt + Entscheidung) und die Lese-Indizes `ix_failure_recommendations_prediction` + `ix_failure_recommendations_machine_created`.
- **`0008_user_subscription_scope`** — ergänzt `users.assigned_line_ids` + `users.assigned_machine_ids` (`bigint[]`, Default `{}`) als Scope-Quelle der F5-WS-/HTTP-Abo-Autorisierung (§20).
- **`0009_event_chain_snapshot`** — ergänzt `reasoner_explanations.chain_snapshot` + `siblings_snapshot` (JSONB, nullable) für den eingefrorenen Ereignisketten-Stand (F5-FE Sektion D, §14.5/§21.15).
- **`0010_audit_trail_topology`** — erweitert `audit_logs` **additiv** (Sektion I): `actor`/`actor_role`/`action_type`/`target_kind`/`target_id`/`machine_id`/`origin`/`detail`/`occurred_at`; CHECK-Constraints auf `action_type`/`origin`; Lese-Indizes (`ix_audit_logs_occurred`/`_action_occurred`/`_machine`/`_target`); ein **Append-Only-Trigger** (PL/pgSQL, `BEFORE UPDATE OR DELETE` weist Mutationen ab — bewusst kein `TRUNCATE`-Trigger, damit Test-/Reset-Pfade leeren können; up/down getestet). Vollständiger Vertrag: **§22**.

---

## 6. Code-Konventionen

- TypeScript strict, kein `any`. Python: mypy strict, ruff, Tests ≥ 85 %.
- Kommentare auf **Deutsch**, Variablen/Funktionen auf **Englisch**.
- Header-Kommentar in jeder Datei (Zweck + Architektur-Einordnung).
- Logs mit Emoji-Prefix. Fehlermeldungen auf Deutsch.
- Mobile-first Tailwind.

---

## 7. Dokumentations-Regel (Definition of Done)

Jeder Implementation-Commit, der Code ändert, **muss** `docs/WALKTHROUGH.md` im selben Commit aktualisieren. Ohne Walkthrough-Update gilt eine Aufgabe als nicht abgeschlossen. So kann die Erklär-Doku nicht von der Realität abdriften.

---

## 8. Sicherheits-/Datenschutz-Leitplanken

- Secrets ausschließlich in `.env` (gitignored). Repo ist öffentlich.
- Anbindung an das Gedächtnis-Substrat nur über Umgebungsvariablen.
- **Werker-bezogene Felder werden pseudonymisiert, NICHT anonymisiert** (deterministische HMAC-SHA-256-Tokenisierung über `users.id`, versionierter Schlüssel, Pepper im Secret-Store). Anonymisierung ist im Industrieumfeld weder vorgeschrieben noch das Ziel; für Nachweis-Felder wäre sie sogar rechtlich falsch. Details: `docs/research/anonymisierung-werkerdaten.md`.
- **Trennung System of Record vs. Reasoning-Schicht:** Der rechtsverbindliche, namentliche Nachweis (Prüf-/Wartungsprotokoll, QM-System, `users`) ist attributierbar unter Art. 6 Abs. 1 lit. c (z. B. BetrSichV §14/TRBS 1203, ArbSchG §6, DGUV). FOREMAN ist **nicht** dieses System of Record für die Signatur — die Nutzdatenbank speichert nur Token; das gilt seit Sektion I auch für **`audit_logs`** (`actor` = HMAC-Token, der Legacy-`user_id`-FK bleibt ungenutzt). Rück-Auflösung Token→Person ist kontrolliert/auditiert und nur für berechtigte Zwecke (Auskunft/Löschung Art. 15/17, HITL-/Behörden-Nachweis).
- Klartext-Identität ausschließlich in `users`; Löschung via Crypto-Shredding (pro-Werker-Schlüssel) — Verhaltensdaten/Maschinen-Gedächtnis bleiben intakt. Löschfristen pro Feld: Nachweis-Felder (`performed_by`, `acknowledged_by`) an gesetzliche Aufbewahrungspflicht gekoppelt, `worker_notes` kürzer.
- **Human-in-the-Loop (BSI):** FOREMAN gibt Empfehlungen, aktoriert nie selbst. Safety-kritische Alarme (`category=safety`) erfordern eine Operator-Quittierung (`alarms.acknowledged_at`/`acknowledged_by`), bevor sie als erledigt gelten.
- **Freitext-Scope der NER-Maskierung:** NER greift in F2 nur auf `worker_notes.text` (das einzige als Werker-Freitext deklarierte Feld). `maintenance_events.description` und `alarms.message` sind als Sach-/SPS-Text gedacht und werden **nicht** maskiert — enthalten sie wider Erwarten Personennamen, bleibt das ein dokumentiertes Restrisiko (organisatorische Regel „keine vollen Namen"; bei Bedarf Redactor später auf diese Felder ausweiten).

---

## 9. Gedächtnis-Substrat — Client-Vertrag & Smoke-Test

Das Substrat wird ausschließlich über einen dünnen HTTP-Wrapper `SubstrateClient` angesprochen. Kein direkter Aufruf aus der Geschäftslogik.

- **Konfiguration:** Base-URL + Token aus `.env` (`SUBSTRATE_BASE_URL`, `SUBSTRATE_TOKEN`). Test-Instanz für Entwicklung.
- **Methoden (HTTP-Operationen des Dienstes):** `remember`, `recall`, `reason`, `drift_status`, `reflect`.
- **Smoke-Test:** beim App-Start und über `GET /api/v1/substrate/smoke` ein `remember` → `recall`-Round-Trip mit einer Test-Erinnerung. Assertion, dass die Erinnerung zurückkommt. Ergebnis als `{ok, latency_ms}`, Log mit Emoji-Prefix.
- **Zweck:** validiert die Substrat-Anbindung, bevor ein Reasoner draufgeht (ersetzt das separate Trainer-Repo in der Fundament-Phase).
- **Fallback:** Datenaufnahme (`readings`, `alarms`) läuft unabhängig vom Substrat weiter, auch wenn der Smoke fehlschlägt — nur das Reasoning ist dann eingeschränkt.

---

## 10. Quality Gates & Pflicht-Checks

Diese Plattform wird nach definierten, überprüfbaren Standards gebaut — nicht „vibe-coded". Jede Änderung durchläuft die folgenden Gates, bevor sie nach `main` gelangt. Rot an einem Pflicht-Gate = kein Merge, kein Deploy.

### 10.1 Definition of Done (pro Implementation-Commit)

Ein Commit gilt erst als fertig, wenn **alle** zutreffen:
- Code + zugehörige Tests im selben Commit.
- `docs/WALKTHROUGH.md` im selben Commit aktualisiert (siehe §7).
- Alle automatischen Gates (§10.2) grün.
- Bei Schema-/Routen-/Type-Änderung: GROUND_TRUTH in diesem Commit nachgezogen.

### 10.2 Automatische Gates (lokal vor Commit/Push)

| Gate | Werkzeug | Schwelle | Ab Phase |
|---|---|---|---|
| Typsicherheit (Py) | `mypy --strict` | 0 Fehler | F2 |
| Typsicherheit (TS) | `tsc --noEmit` | 0 Fehler | F5 |
| Lint (Py) | `ruff check` | clean | F2 |
| Format (Py) | `ruff format --check` | clean | F-SEM |
| Lint (TS) | `eslint` | clean | F5 |
| Tests | `pytest -x` | grün, **Coverage ≥ 85 %** | F2 |
| Komplexität | clean-code-gate | unter Schwelle, keine neuen Smells | F2 |
| Smoke-E2E | `playwright --grep @smoke` | grün | ab F5 (Dashboard) |

Vergleich gegen `.claude-quality-baseline.json` — nur **neu eingeführte** Regressionen blockieren, Alt-Schulden nicht.

### 10.3 Pflicht-Test-Block (jedes Feature)

Jeder Endpoint/Service/Reasoner bringt mindestens mit:
- Happy-Path, Fehlerfall, Auth-/Permission-Fall, Eingabe-/Edge-Validierung.
- Async-Routen via `httpx.AsyncClient` gegen die FastAPI-App.

### 10.4 Security & Privacy (vor Merge nach `main`)

- **Security-Baseline:** OWASP Web Top 10 (2025) + OWASP LLM Top 10 (2025) für Reasoner-/LLM-Pfade + BSI-Zero-Trust-LLM-Prinzipien.
- **Secrets-Scan:** keine Tokens/Keys im Diff (Repo ist öffentlich).
- **Privacy-by-Design (Art. 25 DSGVO):** Werker-bezogene Felder werden im Adapter-Layer **pseudonymisiert** (HMAC-Token, s. §8); Datensparsamkeit; keine PII in Logs. Nachweis-Bezug bleibt attributierbar im System of Record (nicht in FOREMAN).
- **Dependency-Audit:** `pip-audit` / `npm audit`; kritische & hohe CVEs adressiert.
- **Red-Teaming (LLM01) — F6 ✅ scharf:** fester Test-Satz gegen Prompt-Injection über den `worker_notes`-Freitext-Pfad + Grounding-/Halluzinations-Check der Reasoner-Erklärungen, **aktiviert am ersten Reasoner mit LLM-Freitext-Pfad** (Ereignisketten, `tests/reasoners/event_chain/security/test_injection.py`). NICHT ab F4 — der Drift-Reasoner (F4) ist reine Algorithmik (river/ADWIN) ohne LLM-Freitext-Pfad und damit kein Injection-Ziel (siehe §11.2 + §14).
- **Rate-Limiting / Unbounded Consumption (LLM10):** Rate-Limit-Middleware auf der API + Token-/Timeout-/Kosten-Guard im `LLMGateway`.
- **Modell-Integrität / Supply-Chain (LLM03/04):** Modell-Versionen/Digests gepinnt (Ollama-Digest, Anthropic-Model-ID); keine ungepinnte Modell-Auflösung zur Laufzeit. FOREMAN trainiert keine Modelle — daher kein Trainingsdaten-Signatur-Apparat.

### 10.5 Compliance — EU AI Act (Phase 0, vor Code)

- Risiko-Klassifizierung dokumentiert (inkl. Art.-6(3)-Begründung).
- FOREMAN-Voreinschätzung: vermutlich *Minimal/Limited Risk*. **Aber:** Werker-Sicherheitsempfehlungen werden gegen Anhang III (Hochrisiko) geprüft.
- Transparenz (Art. 50(2)): KI-generierte Ausgaben werden als solche gekennzeichnet. **Maßnahme 2 (MCP-Transparenz-Flag) — gebaut (F7):** jeder KI-stämmige MCP-Output trägt `ai_generated`/`generated_by="foreman-ai"`/`requires_human_review`/`model_version` (Vorhersage/Empfehlung zusätzlich `validation_status`/`data_regime`/`validation_caveat`); ein gemeinsamer Wrapper erzwingt die Ehrlichkeit strukturell (Nicht-KI-Daten tragen keine KI-Flags). Vertrag §17. Dashboard-Kennzeichnung (Maßnahme 1, Art. 50(1)) folgt mit F5.
- **Human-in-the-Loop:** keine automatische Aktorik bei safety-relevanten Empfehlungen — der Operator bestätigt (siehe §8).

### 10.6 Deploy-Gate

Vor jedem Deploy die Pre-Deploy-Checkliste komplett grün: `pytest -x` · `mypy --strict` · `ruff check` · (ab F5: `tsc --noEmit` · `npm run lint` · Playwright `@smoke`). Rot → kein Deploy.

---

## 11. Runtime Safety & Observability

Wie sich die Plattform zur Laufzeit verhält — was im Betrieb sichtbar und kontrolliert ist.

### 11.1 Observability (OWASP A09)

- **Strukturierte Logs** pro Reasoner-Aufruf: Latenz, Token-Verbrauch, Kosten, Modell-Backend, Erfolg/Fehler. Emoji-Prefix, keine PII.
- **`/metrics`-Endpoint** im Prometheus-Format: Request-Zähler, Latenz-Histogramme, Token-/Kosten-Counter pro Reasoner & Backend.
- **Grafana-Dashboard** optional (Härtungsphase): Reasoner-Last, Latenz-Verteilung, Modell-Kosten.

### 11.2 Phasen-Zuordnung (pro Phase gebaut, nicht alles vorab)

| Maßnahme | Ab Phase |
|---|---|
| Strukturierte Logs (Latenz/Token/Kosten je Call) | F2 |
| Human-in-the-Loop-Quittierung — Schema | F2 |
| Rate-Limiting (Token-Bucket pro Backend) + `LLMGateway`-Guards (Timeout/Kosten) | **F-LLM ✅ implementiert** (`llm/rate_limit.py`, `llm/gateway.py`) |
| Modell-Digest-Pinning | F-LLM (Config-Pin `local_model_digest` durchgereicht; **keine** Laufzeit-Erzwingung — FOREMAN trainiert nicht, §10.4) |
| Deterministisches Antwort-Caching (gehashter Key, keine PII) | **F-LLM ✅** (`llm/cache.py`) |
| `/metrics`-Endpoint (Prometheus) | F4; **F-LLM ✅** um Gateway-Kennzahlen erweitert (Backend/Task/Latenz/Tokens/Kosten/Fallback/Fehler + Cache-Treffer) |
| Grounding/Spotlighting-Mechanik (Quellenbindung + Post-Check) | **F-LLM ✅** (`llm/grounding.py`) — Mechanik im Gateway; Quellen liefert der Reasoner |
| Red-Team-Harness — **Basis** gegen die Gateway-Mechanik | **F-LLM ✅** (`tests/llm/security/redteam_harness.py`, payload-erweiterbar, grün) |
| Red-Team-Test-Satz — **scharfe Aktivierung** (echte Werker-Freitext-Payloads gegen LLM-Pipeline) | **F6 ✅ scharf am ersten Freitext-Reasoner** (`tests/reasoners/event_chain/security/test_injection.py`) — Harness wiederverwendet gegen die echte Ereignisketten-Pipeline |
| Event-Ketten-Kennzahlen (Erklärungen geflaggt/sauber + NEXUS-Recall-Ausgänge) | **F6 ✅** (`foreman_event_chain_explanations_total`, `foreman_event_chain_recall_total`) |
| Embedding-Kennzahlen (Requests/Latenz/Durchsatz je Backend) | **F-SEM ✅** (`foreman_embed_requests_total` [`backend`/`result`], `foreman_embed_latency_seconds`, `foreman_embed_texts_total`; `observe_embedding`) |
| Ausfallvorhersage-Kennzahlen (Vorhersagen je Datenregime/Entscheidung + Wahrscheinlichkeits-Verteilung) | **F-PRED ✅** (`foreman_failure_predictions_total` [`data_regime`/`decision`], `foreman_failure_probability` [`data_regime`]; `observe_failure_prediction`). **`data_regime=simulation` ist Pflicht-Label auf allen `foreman_failure_*`** — der Sim-Vorbehalt ist im Monitoring sichtbar (§16). |
| Werker-Empfehlungs-Kennzahlen (Empfehlungen je Datenregime/Ausgang + NEXUS-Recall-Ausgänge) | **F-REC ✅** (`foreman_failure_recommendation_total` [`data_regime`/`result` ∈ {issued, rejected_numeric, rejected_overclaim}], `foreman_failure_recommendation_recall_total` [`result` ∈ {hit, miss}]; `observe_failure_recommendation`, `record_failure_recommendation_recall`). **`data_regime=simulation` Pflicht-Label** — der Sim-Vorbehalt bleibt auch über den Erklär-Layer im Monitoring sichtbar (§16). |
| Human-in-the-Loop-Quittierung — Flow im Reasoner | F4 |
| Grafana-Dashboard | Härtung |

> **Red-Team-Präzisierung (F4-Befund).** Ursprünglich war der Red-Team-Test-Satz „ab F4" vorgesehen. Der erste Reasoner (Drift, F4) ist jedoch **reine Algorithmik** (river/ADWIN auf einem aufbereiteten Signalstrom) — er hat **keinen `worker_notes`→LLM-Freitext-Pfad** und ist damit kein Ziel für Prompt-Injection (LLM01). Der Red-Team-Test-Satz (Injection/Grounding/Halluzination) gehört an den **ersten Reasoner mit LLM-Freitext-Pfad** (Event-Ketten-Reasoner, der die natürlichsprachliche Erzählung erzeugt), nicht hierher. In F4 wird kein Red-Team-Set gebaut.

> **Red-Team-Stand (F-LLM).** Mit dem Modell-Gateway steht das **Harness-Gerüst** (`tests/llm/security/redteam_harness.py`): ein wiederverwendbarer, payload-erweiterbarer Satz (Injection-Payloads DE+EN aus `docs/research/prompt-injection-schutz.md` §6) plus Smoke-Tests gegen die **Spotlighting-/Grounding-Mechanik des Gateways** (Datamarking + Delimiter; numerischer Grounding-Post-Check verwirft fabrizierte Zahlen). Das Gerüst ist grün. Die **scharfe Aktivierung** mit echten Werker-Freitext-Payloads gegen eine reale LLM-Pipeline kommt mit dem ersten Freitext-Reasoner (Event-Ketten), der das Gerüst (`INJECTION_PAYLOADS` + `build_worker_note`) konsumiert und das validierte `ReasonerExplanation`-Objekt prüft (Schutz-Doc §5.1/§6). So im Code-Header des Harness vermerkt.

> **Red-Team-Stand (F6 — scharf ✅).** Mit dem Ereignisketten-Reasoner ist die scharfe Aktivierung erfolgt: `tests/reasoners/event_chain/security/test_injection.py` fährt die echten Injection-Payloads (`INJECTION_PAYLOADS`) als `worker_notes`-Freitext (`build_worker_note`) gegen die **reale** Reasoner-Pipeline. Geprüft (Defense-in-Depth, Schutz-Doc §5.1): (1) **Spotlighting hält** — jede Notiz geht datamarkiert als untrusted Quelle ins Gateway, nie als Instruktion; (2) **Output-Guard greift** — selbst ein kompromittiert antwortendes Modell kann keine erfundene Quelle in `referenced_source_ids` schmuggeln (Faktor-Whitelist), unbelegte Zahlen + erfundene `[source]`-Zitate landen in `flagged_unsupported`, die Erzählung wird output-sanitisiert (HTML/Markdown/URL, LLM05), und das `ReasonerExplanation`-Schema validiert (`extra=forbid`); (3) **Inertheit** — der Reasoner erzeugt keine Alarme/Aktorik. False-Positive-Kontrolle (benigne Notiz bleibt sauber) inklusive. Die autoritative Numerik-Abwehr liegt damit architektonisch beim Reasoner (Zahlen nie aus dem LLM als Faktenfeld + Quellen-Whitelist), nicht nur im groben Gateway-Post-Check.

> **Bau-Disziplin:** Diese Maßnahmen sind als verbindliche Gates/Prinzipien dokumentiert, werden aber **pro Phase** gebaut — kein Ops-Vorbau vor dem ersten laufenden Reasoner.

---

## 12. Datenakquise & Adapterschicht (F3)

Die protokoll-agnostische Ingestion-Schicht unter `src/foreman/ingestion/` plus der erste konkrete Adapter unter `src/foreman/adapters/simulation/`.

### 12.1 Internes Normalformat (`ingestion/normalized.py`)

- `NormalizedReading(time [UTC, tz-aware], data_point_id, value, quality|None)` — passt 1:1 auf `readings`.
- `NormalizedEvent` = diskriminierte Union (`kind`): `AlarmEvent`, `ProductionRunRecord`, `MaintenanceRecord`, `WorkerNoteRecord`. Alle Zeitstempel tz-aware UTC (naive → als UTC interpretiert).
- Personen-Felder werden **roh** transportiert (`performed_by_ref`, `author_ref`, `text`) und erst im Service durch den F2-Schreibpfad geschützt — nie Klartext in der DB.

### 12.2 Adapter-Interface & Registry (`ingestion/adapter.py`, `ingestion/registry.py`)

- `SourceAdapter` (ABC) ist die **einzige** Schnittstelle der Ingestion: `name`, `async seed_topology(session)`, `readings()`, `events()`; `stream()` mischt beide zeitlich. Kein Protokoll-/Simulationswissen oberhalb des Adapters.
- Registry: `register_adapter`/`create_adapter`/`load_active_adapters` lädt aktive Adapter per Name. Der Simulations-Adapter registriert sich beim Import unter `"simulation"`.

### 12.3 Ingestion-Service & COPY-Einzigkeit (`ingestion/service.py`)

- `IngestionService.ingest(adapter, *, pace=None)`: seedet Topologie, batcht Readings, schreibt Events.
- **Einziger Reading-Schreibweg:** `copy_readings(session, rows)` (`asyncpg.copy_records_to_table`, Spalten `time, data_point_id, value, quality`). Genutzt von Service **und** `POST /api/v1/readings`. Keine Einzel-Inserts, kein zweiter Weg.
- Diskrete Ereignisse → `alarms` / `production_runs` / `maintenance_events` / `worker_notes`. Personen-Felder: `worker_notes.text` NER-maskiert, `worker_notes.author` + `maintenance_events.performed_by` HMAC-tokenisiert (§8).

### 12.4 Dual-Write ans Substrat (`ingestion/semantic.py`, §9-Fallback)

- `record_semantic_event(...)` schreibt **immer** eine `semantic_events`-Zeile (`event_type`, `payload` jsonb, `machine_id`) und versucht best-effort `SubstrateClient.remember`. Erfolg → `substrate_ref` gesetzt; Fehlschlag/kein Substrat → `substrate_ref = NULL` + Log (Emoji). **Nicht-blockierend:** Substrat-Ausfall blockiert den DB-Schreibpfad nie. Nur diskrete Ereignisse (Alarm/Produktionslauf/Wartung) werden gespiegelt — Werker-Notizen und rohe Readings nicht.

### 12.5 Simulations-Adapter (`adapters/simulation/`)

- **Szenario-Format:** YAML, validiert durch `scenario.py` (Pydantic, strikt). Struktur: `scenario` (Identität + `start` absolut tz-aware, `duration`/`sample_interval` als Dauer-Strings) · `line` · `machine` · `components[]` · `seasonality` (Schichten + Wochenende) · `data_points[]` (Baseline + optional `drift` step|ramp|variance + optional `quality`) · `production_runs[]` · `maintenance_events[]` · `worker_notes[]` · `alarms[]` (Ereignis-Zeiten als Offsets ab `start`) · `ground_truth`.
- **`ground_truth`-Block:** F4-Wahrheit (`drift_present`, `expected_false_alarms`; `primary_drift.t_star`/`expected_detection_window` etc. als Extra-Felder, `extra='allow'`). **Additiv ab F-PRED:** optionales `failure` (strikt, `extra=forbid`): `offset` (Dauer-Offset ab `start`) + `type` (z. B. `bearing_failure`/`tool_failure`). Markiert den Ausfallzeitpunkt eines Degradations-Szenarios; aus ihm leitet `dataset.py` das Positiv-Label im Vorhersagehorizont ab (§16). Die F4-Felder bleiben unverändert gültig (F4-Tests grün). Mit `failure` versehen: `bearing_drift`, `tool_wear`, `lubrication_correlation`; `healthy_baseline` bleibt failure-frei (Negativmaterial).
- **Signale (`signals.py`):** Baseline × Schicht-Last + Gauss-Rauschen, State-Gating über `machine_running`; Drift step/ramp(progressiv)/variance ab bekanntem t*; optional Quality good/bad/missing (missing = Intervall ausgelassen, nicht 0).
- **Seeding (`seed.py`):** idempotent über natürliche Schlüssel (`line.label`, `machine.external_id`, `(machine_id, component.label)`, `(machine_id, data_point.name)`).
- **Runner (`runner.py`):** `python -m foreman.adapters.simulation.runner --scenario <name|pfad> --mode backfill|live [--speed --seed --batch-size --db-url]`. `backfill` = Historie schnell (F4/Dashboard); `live` = Wall-Clock-Takt (Demo). Kein Job-Worker (§3) — Vordergrund-Prozess.
- **Szenarien (`adapters/simulation/scenarios/`):** `bearing_drift`, `tool_wear`, `lubrication_correlation`, `healthy_baseline` (fachlich begründet, F4-Validierungsmaterial) + `minimal_bearing_drift`/`minimal_steady` (Tests/Demo). Fachliche Begründung: `docs/simulation/szenarien.md`.

> **Nicht in F3:** echte Protokoll-Adapter (OPC UA/MQTT/Modbus), Dashboard (F5). Steady-State-Ableitung, Drift-Erkennung/Reasoner und `/metrics` sind in **F4** ergänzt (Drift-Reasoner, §4/§11.2).

---

## 13. LLM-Gateway-Vertrag (F-LLM)

Das Modell-Gateway unter `src/foreman/llm/` ist die **dünne Abstraktion**, auf der jeder kommende LLM-Reasoner aufsetzt (zuerst die Ereignisketten-Rekonstruktion). Tragendes Prinzip — **nicht verhandelbar**: LiteLLM ist ausschließlich Implementierungsdetail hinter dieser Abstraktion. **Ein Reasoner, der `import litellm` enthält, ist ein Architektur-Fehler.** Analog zum SubstrateClient-Vertrag (§9): ein klar umrissener Service-Contract, nicht die Inferenz-Library selbst.

### 13.1 Schnittstelle (das Einzige, was ein Reasoner berührt)

- `LLMGateway` (Protocol, `gateway.py`) — eine `async complete(...)`-Methode, task-typisiert:
  ```
  await gateway.complete(
      task=Task.SYNTHESIS,            # explanation | synthesis | classification
      system_prompt=<Rollen-Instruktion>,
      user_prompt=<die eigentliche Anfrage>,
      sources=[GroundingSource(...), ...],   # optional: Grounding-Kontext
      temperature=None, max_tokens=None,     # optional, Defaults aus Config
  ) -> GatewayResponse
  ```
- `GatewayResponse` (immutable): `text`, `backend`, `model`, `task`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `latency_ms`, `estimated_cost_usd`, `finish_reason`, `grounding` (Report|None), `from_cache`, `fallback_used`.
- `Task` (StrEnum): `explanation`, `synthesis`, `classification` — zugleich niedrig-kardinales Metrik-Label.
- Öffentliche Fläche = `foreman.llm.__init__` (`Task`, `GatewayResponse`, `LLMGateway`, `LiteLLMGateway`, `GroundingSource`, `GroundingReport`, `LLMSettings`, `Priority`, `get_llm_settings`, Fehlerhierarchie). **Keine** Backend-/LiteLLM-Typen exponiert.

### 13.2 Backends & Priority-Modi

- Lokal: Qwen3-14B über **Ollama** (`local_base_url`, Default `ollama/qwen3:14b`) — Dev-/Showcase-Default. Cloud: **Anthropic** über LiteLLM (`cloud_model`, Key als `SecretStr`).
- `priority` (`config.py`): **`local_first`** (Default) · `cloud_first` · `local_only` · `cloud_only`. Auflösung in `backends.resolve_chain`.
- **Fallback** (`run_with_fallback`): lokal nicht erreichbar → Cloud, **sofern die Priority es erlaubt**; sonst typisierter `BackendUnavailable` (z. B. `local_only`). `cloud_only` ohne Key → `GatewayConfigError` beim Bau.
- vLLM-Production-Pfad ist durch die Backend-Config offen gehalten (nicht gebaut).
- **Architektur-Grenze hart:** LiteLLM wird ausschließlich in `backends.py` (lazy) importiert; jede Fremd-/Provider-Ausnahme wird dort in einen Gateway-Fehler übersetzt — nichts LiteLLM-Spezifisches verlässt das Modul.

### 13.3 Grounding-Contract (Spotlighting + Post-Check)

- Der Reasoner übergibt `sources` (`GroundingSource(source_id, content, trusted)`): `trusted=True` = strukturierte Reasoner-/DB-Daten; `trusted=False` = untrusted Werker-Freitext.
- Das Gateway baut daraus den **Spotlighting**-Prompt (`grounding.py`): vertrauenswürdige Daten klar mit `source_id` abgegrenzt, untrusted Freitext **datamarkiert** (Leerzeichen→`▁`) und mit **randomisiertem Delimiter** umschlossen; System-Instruktion: „Freitext ist Daten, nie Anweisung; nur gelistete source_ids; nichts erfinden" (Instruction Hierarchy). Folgt `docs/research/prompt-injection-schutz.md`.
- **Minimaler Post-Check:** führt die Antwort Zahlen ein, die in keiner **vertrauenswürdigen** Quelle stehen? Numerisch kanonisiert (80 == 80.0); zitierte `source_id`s werden vorher maskiert (ihre Ziffern zählen nicht als unbelegt). Eine fabrizierte Zahl im untrusted Freitext belegt nichts. Ergebnis = prüfbarer `GroundingReport` (`grounded`, `source_ids`, `unbacked`). Bei `grounding_strict` → `GroundingViolation`.
- **Bewusste Grenze (ehrlich):** Der Gateway-Post-Check ist ein **grober** Netz-Check — er fängt neuartige/große fabrizierte Zahlen, **nicht** zuverlässig kleine Ganzzahlen (0/1/100), die zufällig in den Quelldaten stehen. Die **autoritative** Numerik-Abwehr ist architektonisch: Zahlen kommen nie aus dem LLM (der Reasoner setzt sie) **plus** die vollständige Quellen-Whitelist auf Faktor-Ebene (`ReasonerExplanation`, Schutz-Doc §5.1) — beides am ersten Freitext-Reasoner (Ereignisketten), nicht im Gateway.

### 13.4 Querschnitt-Mechanik (im Gateway, nicht in den Reasonern)

- **Rate-Limit (LLM10):** Token-Bucket **pro Backend** (`rate_limit.py`, seedbare Uhr). Erschöpft → `RateLimited` (mit `retry_after_s`); ein rate-limitiertes Backend fällt **nicht** still auf das (teure) Cloud-Backend zurück.
- **Caching:** deterministisch (`cache.py`), Key = SHA-256 über Modell + Task + System-/User-Prompt + Quellen + Parameter (**keine PII im Key**). Optional (`cache_enabled`); erzwingt in Tests Byte-Determinismus.
- **Metriken (`/metrics`):** `foreman_llm_*` (requests/latency/tokens/cost/fallbacks/cache_hits) mit Labels `backend`/`task`/`result`/`kind` — niedrig-kardinal, keine PII.
- **Strukturierte Logs** je Call (Emoji-Prefix): Task/Backend/Tokens/Latenz/Fallback/grounded — **kein** Key, **kein** Freitext, **keine** Namen.

### 13.5 Fehlerhierarchie

`GatewayError` (Basis) → `GatewayConfigError` · `BackendUnavailable` (`attempted`) · `RateLimited` (`retry_after_s`) · `GroundingViolation` (`unbacked`) · `GatewayTimeout`. Deutsche Meldungen (§6). Ein Reasoner fängt alles mit `except GatewayError`.

### 13.6 Verifikation

- Unit-Tests gegen ein **deterministisches Mock-Backend** (kein echter LLM-Call) decken Task-Routing, Response-Struktur, alle vier Priority-Modi, Fallback, Rate-Limit, Cache-Determinismus, Grounding und die Gateway-Metriken ab.
- `@pytest.mark.smoke` (`tests/llm/smoke/test_ollama_roundtrip.py`): echter Round-Trip gegen lokales Ollama, **skippt sauber** ohne Ollama — nicht im CI-Pflichtlauf.
- Red-Team-Harness-Basis: siehe §11.2-Notiz.

---

## 14. Ereignisketten-Reasoner-Vertrag (F6)

Der **erste LLM-Freitext-Reasoner** und erste Konsument des `LLMGateway` (§13). Er verknüpft Drift-Events, Werkernotizen, Wartungen und NEXUS-Recall ähnlicher Vergangenheits-Vorfälle zu einer gegroundeten deutschen Erzählung. Modulpfad: `src/foreman/reasoners/event_chain/`.

### 14.1 Pipeline (Schichtung — jede Stufe einzeln testbar)

`reconstruct_chain` (rein) → `recall_similar_incidents` (best-effort) → `build_grounding_sources` → `gateway.complete(task=synthesis, sources=…)` → `build_explanation` (Output-Guard) → Persistenz + Dual-Write.

- **`chain.py` — reiner Kern.** `reconstruct_chain(anchor, window, prior_alarms, worker_notes, maintenance_events) -> EventChain`. Auswahl: identische `machine_id` wie der Anker + Zeitstempel im Fenster; temporale Ordnung. DB-Zugriff injiziert (Reihen werden übergeben) → ohne Netz testbar.
- **`recall.py` — NEXUS-Recall.** Query aus dem Anker-Muster (Maschinenklasse + Alarm-Signatur, **PII-frei**) → `SubstrateClient.recall`. **Strikt best-effort:** kein Substrat / Substrat-Ausfall → leere Recall-Liste, Kette wird ohne Recall-Anteil erzählt (blockiert nie).
- **`grounding_sources.py` — die Sicherheits-Invariante.** Je Ketten-Ereignis + Recall-Treffer eine `GroundingSource(source_id, content, trusted)`. **`worker_notes.text` ist IMMER `trusted=False`** (Spotlighting-Quelle, nie Instruktion); NEXUS-Recall ebenfalls `trusted=False`; nur strukturierte Alarm-/Wartungsdaten sind `trusted=True`. `source_id`-Schema: `alarm:<id>`, `note:<id>`, `maint:<id>`, `recall:<n>`.
- **`prompts.py`.** Deutsche Werker-Erzählung, nur aus den Quellen, Hypothesen markiert, Zitat als `[source_id]`. Der untrusted Notiz-Freitext geht **nur** über die (gespotlighteten) Quellen ins Gateway, nie inline in den User-Prompt.
- **`service.py` — Output-Guard (Schutz-Doc §5.1).** Zitierte Quellen werden gegen die Whitelist geprüft: gültige → `referenced_source_ids`; erfundene → `flagged_unsupported`. Unbelegte Zahlen aus dem Gateway-`GroundingReport` ebenfalls → `flagged_unsupported`. Geflaggt ⇒ `is_hypothesis=True`, `confidence=low`. Die Erzählung wird vor Persistenz **output-sanitisiert** (HTML/Markdown/URL, LLM05). `ReasonerExplanation` ist Pydantic-validiert (`extra=forbid`; `referenced_source_ids ⊆ allowed_source_ids`).

### 14.2 Persistenz & Spiegel

`reasoner_explanations`-Tabelle (§5) + **Dual-Write** des Ergebnisses als `semantic_event` (`event_type=event_chain_reconstructed`, best-effort via `record_semantic_event`, §12.4) — die Reasoner-Erklärung wird Teil des Gedächtnisses. **Gespiegelt wird eine strukturierte, PII-freie Zusammenfassung, nicht der rohe Erzähltext** (defensiv gegen eingeschleusten Freitext im Substrat).

### 14.3 Grenzen (verbindlich)

- **Kein Auto-LLM pro Alarm** — on-demand-Kern; der alarm-getriebene Hook bleibt offen/unverdrahtet (Kostenkontrolle).
- **`worker_notes.classification` wird NICHT genutzt** (leer/nullable; späterer Encoder, nicht in Scope). **`worker_notes.embedding` wird ab F-SEM genutzt** (§15): Im reinen F6-Stand erfolgte die Notiz-Auswahl ausschließlich über `machine_id` + Zeitfenster. Mit F-SEM **ergänzt** die semantische Auswahl (Embedding-Suche) die zeitnahen Notizen — additiv, fenster-exempt, dedupliziert, **best-effort** (Provider/Suche-Ausfall → Fallback auf die reine Zeitfenster-Auswahl, blockiert nie). Die Sicherheits-Invariante bleibt unangetastet: eine Notiz ist `trusted=False`, egal ob zeitlich oder semantisch ausgewählt (`grounding_sources.py` übernimmt das Flag unverändert).
- **Keine Aktorik** — der Reasoner erklärt, schaltet/alarmiert nichts.
- Reasoner importiert **nur** `foreman.llm` (kein LiteLLM-Typ).

### 14.4 Verifikation

Unit-Tests je Stufe (Kette/Recall/Quellen/Output-Guard) ohne Netz; Pipeline-E2E gegen echte DB (Gateway über Mock-Backend des **echten** `LiteLLMGateway`, Substrat aus). **Red-Team scharf** (§11.2): `tests/reasoners/event_chain/security/test_injection.py`.

### 14.5 Ketten-Snapshot & Schwester-Referenzen (F-REC-Erweiterung für FE-Sektion D, §21.15)

Die im `reconstruct`-Service ohnehin voll berechnete `EventChain` (Felder je `ChainEvent`: `source_id`/`event_type`/`occurred_at`/`machine_id`/`summary`/`trusted` + `window`) wird jetzt **ausgeliefert UND eingefroren persistiert**:

- **Response.** `POST /reconstruct` und `GET /explanations/{id}` antworten mit `ReasonerExplanationDetailRead` — ein **Superset** des bestehenden `ReasonerExplanationRead` plus `chain` (die `EventChain`) und `siblings` (`list[SiblingReference]`). Die **Liste** (`GET /explanations`) bleibt bewusst schlank (`ReasonerExplanationRead`). Neuer `GET /explanations/{id}/siblings`.
- **Snapshot (Migration 0009, JSONB).** Zwei nullable JSONB-Spalten auf `reasoner_explanations`: `chain_snapshot` (serialisierte `EventChain`) + `siblings_snapshot` (Liste `SiblingReference`). **Begründung:** Kette + Geschwister werden zur Rekonstruktions-Zeit berechnet, sollen aber als **„Stand X" eingefroren** bleiben (Studie §3.2 Pin/Persist) — ein Re-Fetch leitet NICHT neu ab (Quelldaten — Alarme/Notizen/Wartungen/Substrat — können sich ändern). **JSONB statt FK-Ketten-Tabelle**, weil die Kette eine reine Momentaufnahme ohne eigenen Lebenszyklus ist, atomar mit der Erklärungszeile, konsistent mit dem bestehenden JSONB-Muster der Tabelle (`referenced_source_ids`/`flagged_unsupported`). Nullable → Bestandsdatensätze bleiben gültig (`chain=null`/`siblings=[]`, FE graceful). Migration up/down getestet.
- **Schwester-Referenzen EHRLICH aus realen Recall-Treffern.** `recall.py` zieht je Treffer optionale strukturierte Metadaten (`machine_id`/`machine_class`/`explanation_id`) defensiv aus dem Treffer + seinen Metadaten-Containern; der Service löst fehlende Ziele aus ECHTEN DB-Zeilen auf (Maschinenklasse, jüngste Schwester-Erklärung ≠ aktueller Anker). Eine `SiblingReference` trägt strukturierte Ziele **nur, wenn real auflösbar** (sonst `null`); `similarity_basis` ist die PII-freie geteilte Anker-Signatur, `excerpt` der sanitisierte Kurz-Auszug. **Keine erfundenen Geschwister:** leerer Recall → leere Liste.
- **Invariante unangetastet.** Der Output-Guard (`_enforce_source_whitelist`: `referenced_source_ids ⊆ allowed_source_ids`; `flagged_unsupported` ⇒ `is_hypothesis`) bleibt; die Erweiterung weicht ihn nicht auf. `security/test_injection.py` bleibt grün.

---

## 15. Embedding-Provider & semantische Notiz-Suche (F-SEM)

Die Embedding-Schicht unter `src/foreman/embeddings/` ist die **dünne Abstraktion** für Vektor-Embeddings — eine **parallele, gleich geformte** Schwester des `LLMGateway` (§13), kein Teil davon. Tragendes Prinzip — **nicht verhandelbar**: Embeddings sind ein anderer Pfad als Completion und werden **nicht** in den `LLMGateway` gequetscht; die konkrete Embedding-Library ist ausschließlich Implementierungsdetail in `backends.py`. **Ein Aufrufer (Ingestion/Suche/Reasoner), der `import sentence_transformers` oder einen rohen Ollama-Client enthält, ist ein Architektur-Fehler.**

F-SEM ist eine **Querfunktion**, kein neuer Reasoner: Sie füllt das von F6 bewusst leer gelassene Feld `worker_notes.embedding` und verschiebt die Notiz-Auswahl der Ketten-Rekonstruktion von „zeitnah" auf „zeitnah + relevant". `classification` bleibt draußen (§14.3).

### 15.1 Schnittstelle (das Einzige, was ein Aufrufer berührt)

- `EmbeddingProvider` (Protocol, `provider.py`) — eine `async embed(texts: Sequence[str]) -> list[Vector]`-Methode (Batch): ein Vektor je Text, gleiche Reihenfolge, dimensions-geprüft und (per Default) L2-normalisiert.
- `Vector = list[float]` — ein Embedding-Vektor (Dimension = `EmbeddingSettings.dimension`, passt 1:1 auf `vector(1024)`).
- Öffentliche Fläche = `foreman.embeddings.__init__` (`EmbeddingProvider`, `LocalEmbeddingProvider`, `Vector`, `EmbeddingSettings`, `Priority`, `get_embedding_settings`, `embed_best_effort`, Fehlerhierarchie). **Keine** Backend-/Library-Typen (Ollama/httpx, sentence-transformers) exponiert.

### 15.2 Backends & Priority-Modi

- Lokal-first: **Ollama** mit `bge-m3` (Default, MIT, 1024-dim, stark auf Deutsch) über `POST /api/embed` (Batch via `input`) — derselbe Inferenz-Stack wie das LLM, kein zweites Modell im API-Prozess. Alternative: **sentence-transformers** hinter derselben Schnittstelle (lazy geladen).
- `priority` (`config.py`, env-Prefix `FOREMAN_EMBED_`): **`ollama_first`** (Default) · `st_first` · `ollama_only` · `st_only`. Auflösung in `backends.resolve_chain`; Fallback in `run_with_fallback` (analog Gateway).
- **Architektur-Grenze hart:** die Embedding-Library wird ausschließlich in `backends.py` berührt (sentence-transformers lazy); jede Fremd-/HTTP-Ausnahme wird dort in einen typisierten Embedding-Fehler übersetzt — nichts Library-Spezifisches verlässt das Modul.
- Der Provider **normalisiert L2** und **erzwingt die Dimension** (1024); ein Mismatch wirft `DimensionMismatch` (würde sonst Insert/Index brechen).

### 15.3 Embedding beim Insert (best-effort) + Backfill

- Der bestehende `worker_notes`-Schreibpfad embeddet den (NER-maskierten) `text`: der **Ingestion-Service** (§12.3) als **ein Batch-Call vor jedem Commit**, der **CRUD-`POST /api/v1/worker_notes`** einzeln. Best-effort (`embed_best_effort`, analog Substrat-Dual-Write §12.4 / NEXUS-Recall §14.1): Provider nicht erreichbar → `embedding = NULL`, die Notiz wird **trotzdem** geschrieben; das Embedding blockiert den Notiz-Schreibpfad **nie**.
- **Backfill-Runner** (`embeddings/backfill.py`, `python -m foreman.embeddings.backfill [--batch-size --db-url]`): idempotenter Vordergrund-Prozess (kein Job-Worker, §3), holt `embedding IS NULL` batchweise nach. Anders als der Insert ist der Backfill **ehrlich** (Provider-Fehler propagiert).

### 15.4 Suche (HNSW + Komposition + Route)

- Migration `0004` (§5): HNSW-Index `vector_cosine_ops` (`m=16`, `ef_construction=200`).
- `notes/search.py`: `search_similar_notes(session, query_embedding, machine_id=None, k=…)` — **reine DB-Query mit einem fertigen Vektor** (ohne Provider/Netz testbar) + `embed_and_search(provider, session, query_text, …)` (Komposition: embedden, dann suchen).
- Read-only `GET /api/v1/worker_notes/search` (§4, Auth-pflichtig): ehrlich (503 bei Backend-Ausfall, **nicht** best-effort).

### 15.5 F6-Anbindung (additiv, best-effort, Sicherheit unverändert)

- `chain.reconstruct_chain(…, semantic_notes=…)`: semantisch ähnliche Notizen derselben Maschine **ergänzen** die zeitnahen — **fenster-exempt** (der Sinn der semantischen Auswahl), **dedupliziert über `note.id`**. Default leer → reines F6-Verhalten.
- `EventChainService._load_semantic_notes` baut die **PII-freie Anker-Signatur** (`build_anchor_signature`: Maschinenklasse + Alarm-Code/-Message/-Kategorie; System-/SPS-Text, kein Werker-Freitext) und ruft `embed_and_search(machine_id=anchor.machine_id, k=…)` — **strikt best-effort** (Provider `None` / Suche-Ausfall → Zeitfenster-Fallback, blockiert nie).
- **Sicherheits-Invariante (unverändert):** jede Notiz ist `trusted=False` (Spotlighting-Quelle, nie Instruktion), egal ob zeitlich oder semantisch ausgewählt; `grounding_sources.py` übernimmt das Flag unverändert. Die bestehenden F6-Tests inkl. `security/test_injection.py` bleiben grün.

### 15.6 Fehlerhierarchie

`EmbeddingError` (Basis) → `ProviderUnavailable` (`attempted`) · `DimensionMismatch` (`expected`/`actual`) · `EmbeddingTimeout`. Deutsche Meldungen (§6). Ein Aufrufer fängt alles mit `except EmbeddingError`; der best-effort-Schreibpfad und die F6-Anbindung fangen breit (jeder Fehler → kein Embedding/Fallback).

### 15.7 PII & Verifikation

- **PII:** Embedding-Input ist der bereits NER-maskierte `text`; die Such-Query (Anker-Signatur) ist PII-frei. **Keine** Notiz-Texte, **keine** Vektoren, **keine** Keys in Logs (§8).
- Unit-Tests gegen ein **deterministisches Mock-Backend** (Batch, L2-Normalisierung, Dim-Check, Priority/Fallback, Metriken) ohne Netz; Backend-Tests über httpx-MockTransport (Ollama) bzw. injizierten `encode_fn` (sentence-transformers). DB-Tests gegen echte pgvector/HNSW (Ähnlichkeits-Reihenfolge, `machine_id`-Filter, `k`), Schreibpfad-Tests (best-effort → NULL), F6-Anbindung (semantisch ergänzt, Fallback, `trusted=False`). `@pytest.mark.smoke` (`tests/embeddings/smoke/test_ollama_embed.py`): echter Round-Trip gegen lokales Ollama `bge-m3`, **skippt sauber** ohne Ollama — nicht im CI-Pflichtlauf.

---

## 16. Ausfallvorhersage-Reasoner-Vertrag (F-PRED)

Reasoner #3 unter `src/foreman/reasoners/failure/`. **Bewusst ein ehrlich deklarierter Methoden-Demonstrator:** die Datenlage erlaubt keine echte Ausfallvorhersage (SPS-**Programme** beschreiben, *wie* eine Maschine funktioniert, nicht *was* ihr passiert ist — Ausfälle stehen in **Logs**, die über diesen Kanal grundsätzlich nicht verfügbar sind). Das Modul wird trotzdem vollständig und methodisch korrekt gebaut; sein prädiktiver Wert setzt reale Run-to-failure-Daten voraus. **Ausführliche fachliche Begründung: `docs/models/failure_prediction_model_card.md` (Kern: „Warum Sim-Daten nicht genügen", Verifikation ≠ Validierung).**

### 16.1 Strukturelle Ehrlichkeit (Kern-Deliverable, nicht umgehbar)

- **`FailurePrediction`** (Pydantic, `extra=forbid`) trägt **`validation_status` als PFLICHTFELD ohne Default**, einziger Wert `simulation_only` — es gibt **keinen Konstruktionsweg** ohne den Vorbehalt. Plus `data_regime` (`simulation`) und `model_version` aus den Artefakt-Metadaten. Jeder Konsument (Persistenz, Dashboard, MCP, späterer Erklär-Layer) führt ihn mit.
- **Metrik-Label `data_regime=simulation`** auf allen `foreman_failure_*`-Kennzahlen (§11.2).
- **Persistenz** (`failure_predictions`, §5) führt `validation_status`/`data_regime`/`model_version` als Spalten — der Vorbehalt überlebt die Speicherung.
- **Eval-Metriken sind Funktionsnachweis, kein Realitätsnachweis** — so benannt in Model Card, Code-Header (`train.py`) und Trainings-Log (`train_summary`). Keine Metrik wird als „Genauigkeit der Ausfallvorhersage" verkauft.

### 16.2 Pipeline (Schichtung — jede Stufe einzeln testbar)

`features.extract_features` (rein, netzfrei, **kein Zeit-Leakage**) → `model.predict` (Artefakt laden + Wahrscheinlichkeit + SHAP-`TreeExplainer`-Attribution) → `service` (DB-IO → `FailurePrediction` → Persistenz) → on-demand-Routen (§4).

- **`features.py` — reiner Kern.** Aus einem Vorlauf-Fenster VOR dem Bezugszeitpunkt ein Feature-Vektor: `readings_1m`-Aggregate je Datenpunkt (Mittel/Std/Min/Max/Range/RMS/Trend/RoC/Last), **Drift-Output als Feature** (Anzahl/Stärke/Zeit-seit, Kopplung an F4), Wartung (Zeit seit letzter Wartung), Alarm-Historie. **Strikt `< reference_time`** (getestet); DB injiziert; **PII-frei** (Zahlen über `data_points.name`).
- **`dataset.py` — Trainingsdaten aus Szenarien** (rein/netzfrei über `signals.py`). Label aus `ground_truth.failure` + Horizont *H*; **lauf-disjunkter Split** (Szenario/Seed; kein zeilenweises Mischen); Klassenbalance dokumentiert.
- **`train.py` — Offline-CLI.** `python -m foreman.reasoners.failure.train --scenarios … --seeds 1,2,3,4 --holdout-seeds 4 --horizon-days … --lookback-hours … --step-hours … --seed … --out <artefakt>`. Die Flags `--seeds`/`--holdout-seeds` steuern den **lauf-disjunkten Split** (Läufe mit Holdout-Seed → Eval). LightGBM (binär, `scale_pos_weight = #neg/#pos`, **kein** SMOTE), reproduzierbar (`--seed`), Eval mit **PR-AUC (primär) / ROC-AUC / Brier** (Eval-Holdout muss beide Klassen tragen — sonst Fail-fast), Artefakt + Metadaten (Quelle=`simulation`, Feature-Schema, Horizont, Vorlauf-Fenster, Szenario-Hashes, Seed, Metriken).
- **`model.py` — Inferenz.** Artefakt-Verzeichnis (`model.txt` + `metadata.json`) laden; `predict` (Wahrscheinlichkeit autoritativ vom Modell) + SHAP-Top-Faktoren (`{feature, value, shap, direction}`); fehlende Features → NaN → nicht als Faktor. Gebündeltes Demonstrator-Artefakt: `src/foreman/reasoners/failure/artifacts/failure_lgbm` (Override `FOREMAN_FAILURE_MODEL_PATH`).
- **`service.py` — Orchestrierung.** Lädt `readings_1m`-Reihen, Drift-Events (aus `drift_detected`-`semantic_events`, mit `detected_at`/`effect_size`), Wartung, Nicht-Drift-Alarme; baut die `FailurePrediction` (Vorbehalt erzwungen) und persistiert sie. **Kein Auto-Predict, keine Aktorik.**

### 16.3 Grenzen (verbindlich)

- **Zahlen kommen nie aus einem LLM** (gilt schon hier, damit der spätere Erklär-Layer es erbt; §13.3).
- **Kein Laufzeit-Training** (§10.4) — Training ist ein reproduzierbarer Offline-Schritt, Inferenz lädt nur.
- **On-demand, keine Aktorik** (Konsistenz mit F6, §14.3).
- **SHAP ist assoziativ, nicht kausal** — ein Faktor „erhöht das Risikomodell-Signal", er „verursacht" nichts.
- **Migrationspfad** (Model Card §8): gleiche Feature-Definition, gleiche Trainings-CLI, gleiches Artefakt-Format — nur ein reales, gelabeltes Trainingsset macht aus dem Demonstrator einen validierbaren Prädiktor.

### 16.4 Verifikation

Reine Stufen (Schema/Features/Dataset/Model/Train) ohne Netz; Pipeline-E2E gegen echte DB. **Kern-Akzeptanz:** eine `FailurePrediction` ohne `validation_status` ist nicht konstruierbar, und die E2E-Pipeline trägt `simulation_only` IMMER (`tests/reasoners/failure/`). Kein-Leakage und lauf-disjunkter Split sind getestet.

---

### 16.5 Empfehlungs-Layer (F-REC) — die Ehrlichkeit in die Sprache getragen

Der Erklär-Layer über F-PRED unter `src/foreman/reasoners/failure/` (erweitert das Modul) und **zweiter Konsument des `LLMGateway`** (§13) nach F6. Er macht aus einer bestehenden `FailurePrediction` eine deutsche, handlungsleitende Werker-Empfehlung mit Begründung — das LLM verschmilzt die statistische Vorhersage, die SHAP-Faktoren und den semantischen NEXUS-Kontext (Briefing §4). Modulpfad-Dateien: `recall.py` (NEXUS-Recall ähnlicher Vorlauf-Muster, best-effort), `grounding.py` (Grounding-Quellen), `prompts.py` (System-/User-Prompt), `recommendation.py` (Orchestrierung), `schema.py` (`WorkerRecommendation`), erweiterte `router.py`.

**Pipeline (wie F6, jede Stufe testbar):** `build_runup_query` + `recall_similar_runups` (best-effort) → `build_recommendation_sources` → `gateway.complete(task=explanation, sources=…)` → **numerischer Post-Check** (Invariante I) → **Negativ-Guard** (Invariante II) → `build_recommendation` (Output-Guard + deterministischer Vorbehalt) → Persistenz `failure_recommendations` + Dual-Write `semantic_event`.

**Zwei tragende Invarianten (verbindlich):**
- **(I) Zahlen autoritativ vom Modell.** Wahrscheinlichkeit/Horizont/Entscheidung/SHAP setzt das Modell; das LLM formuliert nur. Die autoritativen Zahlen liegen im `trusted=True`-Content der Vorhersage-/Faktor-Quellen (`pred:<id>`, `factor:<name>`; auch die `machine_id`, damit sie belegt ist). Der Gateway-`GroundingReport.unbacked` wird ausgewertet: **eine unbelegte Zahl → HARTER Reject** (`NumericGroundingError`, keine Persistenz). **Unterschied zu F6:** F6 *flaggt* unbelegte Zahlen (Hypothese), F-REC *rejectet* sie (eine handlungsleitende Empfehlung darf keine erfundene Zahl tragen).
- **(II) Der Sim-Vorbehalt ist deterministisch.** `WorkerRecommendation.validation_caveat` MUSS exakt `validation_caveat_for(validation_status)` sein (Schema-Validator) — er hängt nie am fehlbaren LLM-Text. Zusätzlich rejectet ein Negativ-Guard (`detect_overclaim`) eine Umdeutung des Sim-Charakters im LLM-Text (`RecommendationOverclaimError`). `validation_status`/`data_regime`/`model_version` werden aus der Vorhersage mitgeführt.

**Grenzen:** Werkernotizen bleiben draußen (Kern = Vorhersage + SHAP + Recall; keine F-SEM-Notiz-Einbindung). Recall `trusted=False`, best-effort (Ausfall blockiert nie; Inhalt ist nie Instruktion). On-demand, kein Auto-LLM. Keine Aktorik. Reasoner importiert nur `foreman.llm` (kein LiteLLM-Typ). Dual-Write spiegelt eine PII-freie Zusammenfassung mit `data_regime=simulation`, nicht den rohen Empfehlungstext.

**Verifikation:** reine Stufen (Schema/Recall/Grounding) ohne Netz; Pipeline-E2E gegen echte DB (Gateway über Mock-Backend des **echten** `LiteLLMGateway`, Substrat gemockt/aus). `validation_caveat` IMMER präsent + deterministisch; numerischer Reject getestet; **Red-Team scharf über den Recall-Pfad** (`tests/reasoners/failure/security/test_recommendation_injection.py`): vergifteter Substrat-Inhalt kapert die Empfehlung nicht (Spotlighting hält, Output-Guard greift, numerischer Reject bei fabrizierter Zahl, Vorbehalt nicht umdeutbar, Inertheit).

---

## 17. MCP-Schnittstellen-Vertrag (F7)

FOREMAN als **offener Knoten**: ein read-only Model-Context-Protocol-Server (`src/foreman/mcp/`, Anthropic SDK / FastMCP, **Streamable HTTP**), der die aggregierten Reasoner-Erkenntnisse als saubere, maschinenlesbare Tools an Drittsysteme reicht. Diese Schicht **erfindet keine Logik** — sie exponiert das schon Gebaute. Eigenständige ASGI-App, getrennt von der Plattform-FastAPI-App (eigener Port, eigener Token).

### 17.1 Drei tragende Invarianten

- **(I) Read-only, keine Aktorik, keine Reasoner-Trigger.** Jedes Tool ist `readOnlyHint=True` und liest ausschließlich (SELECT) über die MCP-eigene Read-Schicht `reads.py`. Kein Tool ruft je `predict`/`recommend`/`reconstruct`/`run_machine` oder das `LLMGateway` — das sind Compute+Write+LLM-Pfade und bewusst draußen. Damit behält FOREMAN die Kontrolle über Aktion **und** LLM-Kosten; zugleich ist das die tragende AI-Act-Limited-Risk-Bedingung (§10.5, keine Aktorik). Strukturell verifiziert: `tests/mcp/security/test_no_actuation.py` (kein Schreib-/Trigger-Muster im Quelltext, alle Tools nicht-destruktiv).
- **(II) AI-Act-Transparenz an jedem KI-Output (Art. 50(2)).** Ein gemeinsamer Wrapper `AiTransparency` (`transparency.py`) hüllt jeden KI-stämmigen Output: `ai_generated`/`generated_by="foreman-ai"`/`requires_human_review`/`model_version`; bei Ausfallvorhersage und Empfehlung zusätzlich `validation_status`/`data_regime`/`validation_caveat`. Die Ehrlichkeit ist **strukturell** erzwungen (ein Validator lässt weder einen KI-Umschlag ohne Marker noch einen Nicht-KI-Umschlag mit KI-Metadaten zu). Ereignisketten persistieren keine Modell-Version → `model_version` ehrlich null. Nicht-KI-Daten (Stammdaten, Readings, Alarme) werden **nicht** als KI gekennzeichnet.
- **(III) IP-Wording (nach außen sichtbar).** Tool-Namen/-Beschreibungen/-Schemata tragen **kein** internes Vokabular (kein Library-/Algorithmen-/Substrat-Name); das Gedächtnis nur paraphrasiert. SHAP heißt nach außen `contribution`. **Hidden-Term-Scan als Akzeptanzkriterium:** `tests/mcp/security/test_ip_wording.py` scannt alle Tool-Strings (Name + Beschreibung + Ein-/Ausgabeschema).

### 17.2 Schnittstelle

- **Transport/Auth:** `POST/GET /mcp` (Streamable HTTP), Bearer-`FOREMAN_MCP_`-Token (`SecretStr`, zeitkonstanter Vergleich, Fail-Closed). Fehlend/ungültig → 401; Abruf-Last über das Token-Bucket → 429. Produktions-Fail-Fast: kein remote erreichbarer Server ohne sicheren Token (`require_secure_token`). Offen (kein Token): `GET /health`, `GET /metrics`.
- **Read-Schicht (`reads.py`) als sauberer Service-Layer:** Architektur-Entscheidung (Review-geklärt) — die Read-Logik der Reasoner lag bisher inline in den HTTP-Routern, ohne wiederverwendbare Service-Methode. Statt sechs bestehende Router zu refactoren, bekommt MCP eine eigene, injizierte (Session), testbare Read-Schicht. Die Service-Klassen der Reasoner (Compute/Write/LLM) werden **nicht** angefasst.
- **Tools (11):** `list_machines`, `get_machine`, `get_drift_status`, `get_alarms(machine_id?, since?, severity?)`, `list_failure_predictions(machine_id?)`, `get_failure_prediction(prediction_id)`, `get_worker_recommendation(prediction_id)`, `list_event_chains(machine_id?)` (filtert auf den Ereignisketten-Reasoner), `get_event_chain(explanation_id)`, `search_notes(query, machine_id?, k?)` (bettet die Query ein + sucht — billig, kein LLM), `get_readings(machine_id, datapoint, hours?)` (aggregierter Trend über die Minuten-Aggregat-Sicht). Maschinen-`status` (gesund/Drift aktiv/offene Warnung) wird aus offenen Alarmen komponiert.
- **PII (§8):** nur pseudonymisierte/maskierte Formen raus — `acknowledged_by`/`author` als HMAC-Token (nie aufgelöst), `worker_notes.text` NER-maskiert. Kein Embedding-Vektor, keine `users`-Felder, keine internen Re-ID-Schlüssel. Verifiziert: `tests/mcp/test_pii.py`.
- **Vorbehalt überlebt die MCP-Grenze:** F-PRED-Outputs tragen `validation_status=simulation_only`/`data_regime`/`model_version`; F-REC-Outputs zusätzlich den gespeicherten deterministischen `validation_caveat`. Diese Felder werden vom MCP-Layer nie abgestreift.

### 17.3 Grenzen & Observability

- **Nicht in Scope (bewusst):** Reasoner-Trigger über MCP, Schreib-Tools, Dashboard. Reasoner-Trigger via MCP wäre eine spätere, eng abgesicherte Erweiterung (gäbe einem Drittsystem Kontrolle über LLM-Kosten/DB-Seiteneffekte und rückte an die Aktorik-Grenze).
- **Metriken:** `foreman_mcp_requests_total` (`tool`/`result`) + `foreman_mcp_latency_seconds` (`tool`), niedrig-kardinal, keine PII — unter der eigenen `/metrics`-Route des MCP-Servers.
- **Verifikation:** `tests/mcp/` — Transparenz-Ehrlichkeit, Tool-Korrektheit + Read-only (keine Seiteneffekte), Auth-Reject, PII-Schutz, SDK-Handshake (Tool-Registry), No-Actuation + Hidden-Term-Scan. Coverage der Schicht ≥ 85 %.

---

## 18. Privacy & Compliance

> Pflicht-Sektion (siehe Skill `ground-truth-check`). Verdichtet die §8-Leitplanken zu den geforderten benannten Feldern; die ausführliche Herleitung liegt in `docs/compliance/`.

- **AI-Act-Klassifizierung:** **Limited Risk** (Art. 50 Transparenz + Art. 4 KI-Kompetenz), Stand Juni 2026. Begründung: keine verbotene Praktik (Art. 5), kein Hochrisiko (Anhang I/III verneint — Fabrik ≠ kritische Infrastruktur, kein HR-/Personal-Scoring, kein in eine konformitätspflichtige Maschine integriertes ML-Sicherheitsbauteil). **Tragende Bedingung:** Human-in-the-Loop ohne automatische Aktorik. Quelle: `docs/compliance/eu-ai-act-assessment.md`. Re-Assessment bei Architektur-Änderung (Aktorik, neue Datenarten, Personenbezug).
- **DSFA-Status:** vorläufige Datenschutz-Folgenabschätzung in `docs/compliance/dsfa-foreman-vorlaeufig.md`; vor echtem Produktiveinsatz (reale Werkerdaten) zu finalisieren.
- **VVT-Eintrag:** Verarbeitungstätigkeiten in der DSGVO-Einschätzung skizziert (`docs/compliance/dsgvo-assessment.md`); formales VVT vor Produktiveinsatz pro Betreiber zu führen.
- **AVV:** Default-Pfad ist **lokal** (Qwen3/Ollama) → keine Auftragsverarbeitung durch Dritte. **Cloud-Fallback (Anthropic):** AVV nach Art. 28 DSGVO + Werker-Freitext-Pseudonymisierung/NER **vor** Versand erforderlich, bevor der Fallback produktiv genutzt wird (Stand: offen, kein Produktiveinsatz).
- **Drittlandtransfer:** Default **EU-only / lokal** (kein Transfer). Bei Cloud-Fallback: Transfer-Grundlage (SCC/Angemessenheit) pro Anbieter vor Nutzung zu prüfen.
- **Speicherdauern pro Datenkategorie:** Nachweis-Felder (`performed_by`, `acknowledged_by`) an gesetzliche Aufbewahrungspflicht gekoppelt; `worker_notes` kürzer; Sensorzeitreihen über TimescaleDB-Retention gestaffelt (Roh `readings` 90 d, `readings_1m` 1 J, `readings_1h` 5 J, `readings_1d` unbegrenzt). MCP gibt nur aggregierte/maskierte Formen aus.
- **Lösch-Konzept:** Crypto-Shredding über pro-Werker-Schlüssel (§8) — Klartext-Identität nur in `users`; Löschung trennt die Person vom Token, Verhaltens-/Maschinen-Gedächtnis bleibt intakt (Art. 17 DSGVO). MCP hält keinen Schlüssel und kann Token nicht auflösen.

---

## 19. Security

> Pflicht-Sektion (siehe Skill `ground-truth-check`). Verdichtet §10.4 + die F6/F-REC/F7-Härtung zu den geforderten benannten Feldern.

- **Threat Model:** LLM-/Reasoner-Pfade nach OWASP LLM Top 10 (2025) + OWASP Web Top 10 (2025) + BSI-Zero-Trust-LLM-Prinzipien (§10.4); Prompt-Injection-Analyse in `docs/research/prompt-injection-schutz.md`.
- **Letzte Pen-Test / Red-Team:** scharfer Red-Team-Test-Satz an den LLM-Freitext-Pfaden — F6 (Ereignisketten, `tests/reasoners/event_chain/security/`) ✅ und F-REC (Recall-Pfad, `tests/reasoners/failure/security/`) ✅; F7-MCP strukturell (No-Actuation + Hidden-Term-Scan + PII-Test, `tests/mcp/security/` + `tests/mcp/test_pii.py`) ✅, Stand Juni 2026. Externer Pen-Test: vor Produktiveinsatz.
- **SBOM:** Abhängigkeits-Manifest in `pyproject.toml` + `uv.lock`; SBOM/Audit über die Dependency-Audit-Routine (`pip-audit`) erzeugbar — kein persistiertes SBOM-Artefakt im Repo (Stand F7).
- **OWASP LLM Top 10 Coverage:** LLM01 (Prompt-Injection) — Spotlighting + Output-Guard + Red-Team ✅; LLM02/05 (Output-Handling) — Sanitisierung + Datamarking ✅; LLM03/04 (Supply-Chain/Modell-Integrität) — Modell-Version/Digest gepinnt ✅; LLM10 (Unbounded Consumption) — Token-/Timeout-/Kosten-Guard im Gateway **und** Token-Bucket-Rate-Limit am MCP-Server ✅. MCP-spezifisch: read-only (keine Schreib-/Trigger-Angriffsfläche), Fail-Closed-Auth.
- **BSI-Zero-Trust-Compliance:** Human-in-the-Loop, keine automatische Aktorik; Safety-Alarme nur über Operator-Quittierung erledigt (§8); MCP exponiert nichts Schaltbares.
- **MCP-Server-Hardening (F7):** read-only strukturell bewiesen; dedizierter `SecretStr`-Token getrennt vom Plattform-JWT (zeitkonstanter Vergleich, Fail-Closed, Produktions-Fail-Fast); Rate-Limit (429); Hidden-Term-Scan; PII nur pseudonymisiert/maskiert (Token nie aufgelöst); eigenständige App (eigener Port). Stand: F7 ✅.
- **Dashboard-Live-Push-Hardening (F5):** WebSocket-Scope wird von der AuthMiddleware durchgelassen → **manuelle** Token-Auth im Endpoint (Close 4401, vor `accept`); pro `subscribe` eine **Autorisierung** (default-deny, Rollenmatrix + Per-User-Scope) — ein authentifizierter Client kann nicht jedes Maschinen-Thema mithören (PII-Pfad). Dieselbe Prüfung gilt für die HTTP-Read-Routen (§4/§20.4). NOTIFY-Payload trägt nur IDs (keine Nutzlast); der Kanal ist read-only (keine Aktorik). Stand: F5 ✅.

---

## 20. Dashboard-Backend & Live-Push (F5)

Das Backend-Fundament des Dashboards (Frontend folgt separat). Trennt **LIVE** (Push/WebSocket) von **ON-DEMAND/Erstbild** (Pull/HTTP, §4) und teilt einen transport-neutralen **Read-Core**. Designgrundlage: `docs/research/FOREMAN_Designstudie_Frontend.md` §5.1.

### 20.1 Geteilter Read-Core (`foreman/reads/`)
Transport-neutrale Read-only-Schicht, von MCP (F7), HTTP-Routen (§4) und WS-Push gemeinsam genutzt — keine Duplikation. `queries.py` (SELECT-Funktionen + `ReadingBucket`), `status.py` (`compose_status` + kanonischer `MachineStatus` healthy/drift_active/open_warning), `overview.py` (`build_fleet_overview(machine_ids?)` → FCSM-Status + Severity-Breakdown + Rollup), `trend.py` (`build_trend`/`build_trend_by_id` → `readings_1m` + statisches Normalband). Die MCP-Schicht (F7) ruft jetzt diesen Read-Core auf (vormals `mcp/reads.py` + `_compose_status` — verschoben, F7-Verhalten unverändert).

### 20.2 Transport: Postgres LISTEN/NOTIFY (kein Polling, kein Redis)
Der separate Ingest-Prozess (§12.5) ist nicht die API → entkoppelte Push-Brücke über Postgres-NOTIFY (Stack bewusst ohne Redis/Celery).
- **Producer (`realtime/notify.py` + `channels.py`):** der geteilte Schreibpfad feuert **ein** `pg_notify` pro Commit/Batch (NICHT pro Zeile) auf Kanal `foreman_dashboard`, transaktional (Zustellung beim Commit). Dünner Payload (nur IDs: `machines`/`data_points`/`kinds`; Overflow > 7 KB → `broad`-Signal statt stiller Truncation). Verdrahtet in `ingestion/service.py` (ein NOTIFY je Tick-Commit; nur live-relevante Readings/Alarme — nicht Wartung/Läufe/Notizen) und `POST /api/v1/readings`.
- **Consumer (`realtime/listener.py` + `hub.py`), PRO Worker:** je Uvicorn-Worker eine dedizierte asyncpg-LISTEN-Verbindung + ein In-Process-Hub (kein globaler Singleton; Postgres broadcastet an alle Worker, jeder bedient seine eigenen Clients). Der Hub mappt das ChangeSet auf Themen und **debounct pro Thema → lädt dann** konsolidiert über den Read-Core (Reihenfolge: debounce→load). (Re)Connect → breites Refresh (Snapshot-Reload, keine fire-and-forget-Lücke). Verdrahtung im Lifespan (`realtime/wiring.py`); `start()` wartet auf die erste Verbindung, damit ein unmittelbar folgendes NOTIFY nicht verloren geht.

### 20.3 WebSocket-Vertrag (`/api/v1/ws`, `realtime/ws.py`)
EIN gemultiplexter Kanal, Themen-Abos `overview` / `machine:{id}` / `trend:{data_point_id}`. Auth per Query-Token (Close 4401, vor `accept`) — das Token ist ein Session-JWT **oder** ein kurzlebiges WS-Ticket (`aud="ws"`, §4 `GET /api/v1/ws-ticket`); `decode_ws_token` akzeptiert beide, lehnt fremde `aud` ab. So muss das Frontend nicht das volle Session-JWT für den WS herausgeben. Pro `subscribe`: Autorisierung (default-deny, §20.4) → sofortiger Snapshot → danach Live-Deltas. State-Schichtung (Designstudie §5.1): Stream-State (NOTIFY) → debounce → abgeleiteter View-State (Read-Core, auf Anzeigeauflösung downgesampelt) → Push. Pro Lade-Operation eine kurze Read-only-Session (keine Dauer-Session je Verbindung, blockiert keine Pool-Verbindung). **Keine Aktorik** — der Kanal trägt Zustand, schreibt nie.

### 20.4 Abo-Autorisierung (`realtime/authz.py`) — PII-Strich
Beim `subscribe` und in jeder HTTP-Read-Route wird nicht nur authentifiziert, sondern **autorisiert** (`can_subscribe`, default-deny), damit kein authentifizierter Client jedes Maschinen-Thema mithört. Rollenmatrix (Designstudie 3.1): `manager`/`technician` unrestricted; `shift_lead` → Maschinen seiner Linien (`users.assigned_line_ids`); `worker` → seine Maschinen (`users.assigned_machine_ids`); `overview` nur `manager`/`shift_lead`. Trend-Themen erben den Maschinen-Scope ihres Datenpunkts. **Dieselbe** Prüfung für WS UND HTTP (§4) — der Strich hält auf beiden Transporten, nicht erst im Frontend. Scope-Quelle: §5 `users.assigned_*` (Migration `0008`), hinter einem Resolver-Seam austauschbar.

### 20.5 CAGG-Aktualität & Eigenprofil
Der Trend liest `readings_1m` (real-time aggregation, `materialized_only=false` aus `0002`) — der jüngste, noch nicht materialisierte Bucket ist ohne Refresh sichtbar, die Live-Kurve hinkt dem Puls nicht hinterher (Test verifiziert). Das **statische** Normalband (`normal_min`/`normal_max`) liegt im Trend; das **dynamische zustandsspezifische Drift-Eigenprofil** (F4) ist nicht persistiert (gegateter Replay, `reasoners/drift`) und folgt als eigener Schritt — das Transport-Feld `profile_band` (`MachineTrendOut`) ist dafür reserviert (nullable, derzeit immer null).

### 20.6 Verifikation
Read-Core (overview/trend inkl. CAGG-Frische ohne Refresh), NOTIFY-Producer (ein NOTIFY/Commit, transaktional), Hub (debounce/coalescing/broad/unsubscribe), Listener (NOTIFY→Hub, Reconnect-broad), Authz (default-deny + Rollenmatrix + Per-User-Scope), WS-Endpoint (Auth-Reject, Snapshot, Forbidden, **echter E2E-Push** POST→NOTIFY→Listener→Hub→WS) und beide HTTP-Routen — `tests/unit/test_realtime_*`, `tests/integration/test_realtime_*`, `tests/integration/test_dashboard_*`, `tests/unit/test_dashboard_schemas.py`. Gates wie §10 (mypy --strict, ruff, Coverage).

---

## 21. Frontend (F5-FE Fundament)

Der Werker-Output-Kanal. **Verbindliche Designgrundlage:** `docs/research/FOREMAN_Designstudie_Frontend.md`. Monorepo-Unterordner `frontend/`. Drei bleibende Haltungen als Verfassung: Simulations-Vorbehalt sichtbar · Human-in-the-Loop ohne Aktorik · Gedächtnis nach außen paraphrasiert (Hidden-Term-Scan vor PR).

### 21.1 Stack & Struktur
Next.js 15 App Router, React 19, TypeScript **strict** (`noUncheckedIndexedAccess`, kein `any`), Tailwind CSS 4 (CSS-first, kein Standard-Theme), Vitest + Testing Library, ESLint (next) + Prettier. Mobile-first. Struktur: `frontend/tokens/` (Token-Quelle), `frontend/lib/{realtime,state,auth,ui,api}/`, `frontend/components/{atoms,shell}/`, `frontend/views/`, `frontend/app/` (App Router + BFF-Route-Handler).

### 21.2 Token-Quelle (Design-System, Studie §5.7)
Drei Ebenen: **primitive** (`tokens/primitive.ts`, Rohwerte) → **semantic** (`tokens/themes.ts`, `SEMANTIC_COLOR_TOKENS`) → **theme** (`dark` primär + `hc-light` gleichwertig). Generator `scripts/build-tokens.ts` → `app/styles/tokens.generated.css` (Tailwind `@theme` + Runtime-CSS-Variablen). `npm run tokens:check` ist das CI-Sync-Gate (committete CSS == Quelle). UI referenziert **nur** semantische Utilities (`bg-surface-canvas`, `text-fg-primary`, `bg-state-ok`, `text-note-caveat`, `border-line-subtle` …). Paletten: neutrale UI, ISA-18.2 (`alarm-*`), NE-107 FCSM (`state-*`), Vorbehalt (`note-caveat`, **kein** Rot), entsättigte Daten/Heatmap, Differenz blau↔orange. **Kontrast automatisiert** (`tokens/contrast.test.ts`): Status-Text ≥7:1, Körper ≥4.5:1, Grafik ≥3:1 — beide Themes.

### 21.3 Echtzeit-/State-Schicht (Kern, Studie §5.1)
Strikte Transport-Entkopplung: `Transport`-Interface (`lib/realtime/transport.ts`) → `WebSocketTransport` (`lib/realtime/ws-client.ts`, gegen **realen** WS-Vertrag: `{action,topic}` / `{type,topic,data|reason}`, Themen `overview`/`machine:{id}`/`trend:{data_point_id}`, `?token=`, Close 4401, Reconnect→Re-Subscribe=Snapshot-Reload) → `RealtimeStore` (`lib/realtime/realtime-store.ts`, Stream-State: gepuffert+gedrosselt, Backpressure). Abgeleitete Ebene `lib/state/view-state.ts` (fünf Pflichtzustände, Degradation friert ein). React via `useSyncExternalStore` (`lib/state/use-topic.ts`). **Visualisierung kennt den Transport nie** — transport-agnostisch testbar gegen `FakeTransport`.

### 21.4 Backend-Anbindung (BFF — kein CORS-Eingriff, chirurgisch)
Next.js-Route-Handler-Proxy `app/api/v1/[...path]/route.ts` liest das JWT aus dem **httpOnly-Cookie** `foreman_token` und injiziert es als Bearer → das Backend braucht keine CORS-Lockerung. `app/api/session/route.ts` (Login → `/auth/login` + `/api/v1/me`, setzt Cookie; Logout; GET Session). `app/api/ws-ticket/route.ts` liefert dem Client das WS-Ticket just-in-time. Rolle/Scope kommen aus **GET /api/v1/me**. WS verbindet direkt zum Backend über `NEXT_PUBLIC_FOREMAN_WS_URL` (Route-Handler proxien kein WebSocket).

### 21.5 Atome & Shell (Studie §5.5/§3.3)
Atome: `StatusIndicator` (FCSM mehrkanalig: Farbe+Kürzel+Label), `ProvenanceStamp` (Herkunft/Stand + AI-Act-Kennzeichnung), `KpiTile` (nie nackte Zahl), Fünf-Zustände-Hülle (`lib/ui/five-states.tsx`). Shell: `GlobalStatusBar` (live), `ScopeBreadcrumb`, `CommandPalette` (⌘K), `QuickCaptureFab`, `PrimaryNav` (rollengefiltert ≤7). Dark + HC-Light umschaltbar, drei Dichte-Modi, Touch-Ziele ≥56/64px, sichtbarer Fokusring, reduced-motion.

### 21.6 Rollen & Routen je Sektion (wachsende Tabelle)
Rollenmatrix 3.1 als durchsetzbare Daten (`lib/auth/roles.ts`, `ACCESS_MATRIX`); **Sichtbarkeit ≤ Server-Autorisierung** (Server-Guard `lib/auth/guard.ts`, default-deny, Direktaufruf nicht erlaubter Sektion → rollenspezifisches Landing). Reifegrade aus der Studie.

| Sektion | Route | Reifegrad | Frontend-Stand |
|---|---|---|---|
| A Flotten-Cockpit | `/overview` | [KERN STEHT] (föderiert/WebGL = [VISION]) | ✅ voll: bespoke SVG-DriftHeatmap (Klasse×Maschine, entsättigte sequenzielle Intensität + Schraffur + FCSM, severity-frei), KPI-Zeile (`KpiTile`), Prioritätsspalte, Föderations-Scope (`ScopeBreadcrumb`, Mehr-Werk = markiertes Zielbild), Live ohne Sprung + Kipp-Puls, Matrix tastaturnavigierbar, Rollen-Varianten (§21.14). Löst den FE1-Durchstich ab (live gegen `/api/v1/overview` + WS, rollengefiltert) |
| B Maschinen-Detail | `/machines` · `/machines/[id]` | [KERN] | ✅ voll: bespoke SVG-TimeSeriesChart (Normalband-Fläche, Drift-Akzent, Eigenprofil graceful), Kopf/Specs/Historie (PII)/Alarme (C-`AlarmRow`), Rollen-Varianten (§21.11) |
| C Alarme | `/alarms` | [STEHT] | ✅ voll: ISA-18.2-gestaffelt, virtualisiert, Live-Insert, HITL-Quittierung, Eskalation, Rollen-Varianten (§21.9) |
| Erkenntnisse-Hub | `/insights` | — | ✅ Dach D/E/F/G mit Sekundärnav (D/E live, F/G graceful) |
| D Ereignisketten | `/insights/chains` | [STEHT] | ✅ voll: zweispaltige `TimelineNarrative` (belegt vs. erzählt hart getrennt, bespoke SVG-Symbole, gekoppeltes Hervorheben), On-Demand-Trigger gegen Anker-Alarm, ehrliche Schwesterketten, Pin an B (eingefrorener Stand), Rollen-Varianten (§21.15) |
| E Ausfallvorhersage | `/insights/prediction` | [STEHT] | ✅ voll: ConfidenceCaveatCard (Vier-Block, Vorbehalt untrennbar), geteiltes On-Demand-Muster, HITL-Entscheidung, Rollen-Varianten (§21.10) |
| F Wartung | `/insights` (Hub) | [VISION] | Platzhalter |
| G Belastung (Lastprofil-Historie) | `/insights` (Hub) | [VISION] | Platzhalter — **Anzeige** beobachteter Lastprofile/Grenzwerte, ausdrücklich **kein Simulator** (Lastdaten als MCP-Datenfähigkeit, §2/§17); G-FE folgt separat |
| H Gedächtnis | `/memory` | [KERN] | ✅ voll: Bedeutungssuche (On-Demand), Relevanz=Position (kein Prozent), Verdichtung + Verknüpfung graceful, PII, Cmd-K → H, Rollen (§21.12) |
| I Plattform | `/platform` | [STEHT] (FE) · ehrliche Teilmenge von §4I [VISION] | ✅ voll: ruhige nicht-animierte bespoke-SVG-Systemtopologie (FOREMAN-Zentrum, Eingänge/Substrat/MCP-Grenze, [VISION] abgesetzt/nie verbunden) + eigener mehrkanaliger Verbindungsstatus (NE-107-Geist, `unbekannt` ehrlich neutral — bewusst NICHT das Fcsm-`StatusIndicator`-Atom, das kein `unbekannt` kennt) + unveränderlich-lesende Audit-Tabelle (monospace-IDs, `actor` pseudonym `#hex6`, Filter+Pagination auf die realen Query-Params). Rollen-Split: Manager Topologie+Audit (Tabs) · Schichtleiter nur Topologie (FE ruft `/audit` nie auf) · Werker/Techniker `requireSection`-Landing. HTTP-Snapshot + manueller Refresh (kein WS-Feed). Rollen-Varianten (§21.17) |
| J Erfassung | `/capture` | [KERN] | ✅ voll: reibungsarmes Formular (Freitext zuerst, vorbefüllte Zuordnungs-Chips, Kategorie mehrkanalig), Offline-Queue mit Sync-Status (Lösch-nach-Senden), Kontext-Vorauswahl aus B/Alarm/FAB, dezente Brücke zu H, Rollen-Varianten (§21.13) |
| Anmeldung | `/login` | — | ✅ |

### 21.7 Env & Gates
Env: `FOREMAN_API_URL` (server, Default `http://localhost:8000`), `NEXT_PUBLIC_FOREMAN_WS_URL` (Client-WS, z. B. `ws://localhost:8000/api/v1/ws`). Gates: `npm run typecheck` (tsc strict 0), `npm run lint` (ESLint 0), `npm test` (Vitest), `npm run build`, `npm run tokens:check`. CI: `.github/workflows/ci.yml` Job `frontend-gates` (Node 24) erzwingt diese Gates pro PR.

### 21.8 Bewusst verschoben (eigene Prompts/Schritte)
Die zehn Sektionen (C/E zuerst). WebGL (A/G), Sprach-UI (J-Vision), Electron, Service-Worker-Vollausbau, Playwright-E2E (Durchstich derzeit als Vitest-Integrationstest auf Transport-Ebene), Font-Selfhosting. Erstbild Shared-JS ~102 kB (nahe Studien-Ziel <100 kB; schwere Teile sektionsweise lazy).

**Security-Follow-ups (aus dem adversarialen Review, bewusst offen):**
- **Kurzlebiges WS-Ticket:** ✅ **ERLEDIGT.** Backend `GET /api/v1/ws-ticket` (#21) prägt ein kurzlebiges (60 s), WS-scoped Ticket (`aud="ws"`); der WS akzeptiert es (oder ein Session-JWT), HTTP-Routen lehnen `aud`-Tokens ab. Das Frontend (`app/api/ws-ticket`) holt dieses Ticket und gibt **nur** dieses an Browser-JS heraus — nie das Session-JWT (bleibt im httpOnly-Cookie). Bei Query-/JS-Leak ist nur ein kurzlebiges Nur-WS-Ticket exponiert.
- **WS-Transportweg:** Live-Updates brauchen `NEXT_PUBLIC_FOREMAN_WS_URL` (direkter Backend-WS) oder einen WS-Reverse-Proxy am Frontend-Origin — der HTTP-BFF-Proxy reicht kein WebSocket-Upgrade weiter. Ohne das bleibt die Sicht auf dem HTTP-Snapshot.

### 21.9 Sektion C — Alarme & Warnungen (F5-FE Prompt 2, [STEHT])

Erste voll ausgebaute Sektion auf dem FE1-Fundament. Leitfrage: „Was verlangt jetzt meine Entscheidung — in welcher Reihenfolge?" Designgrundlage: Studie §4C (+ §2/§3.2/§5.2/§5.5/§5.6/§5.8).

- **Reine View-State-Logik (`frontend/lib/alarms/`)** — transport-agnostisch, ohne UI testbar: Severity→Prioritäts-Tier (`priority.ts`; emergency+critical → kritischer Rot-Tier, max. eine dominante Rot-Fläche), Lebenszyklus aus Zeitstempeln (`lifecycle.ts`: `cleared_at`→geklärt, sonst `acknowledged_at`→quittiert, sonst aktiv — das Backend hat **kein** lifecycle-Feld), Sortierung (`sort.ts`: kritisch oben, aktiv vor quittiert, Notfall vor Kritisch, jüngste zuerst — nicht chronologisch-flach), Gruppierung Priorität/Bereich/Maschine (`group.ts`), Flood-Bündelung (`flood.ts`), Zähler inkl. live aus dem overview-Aggregat (`counts.ts`), Live-Insert-Diff (`diff.ts`), Virtualisierungs-Mathematik (`window.ts`), PII-Maskierung (`mask.ts`: `acknowledged_by`-HMAC-Token → `#hex6`, nie Klartext), Rollen-Varianten (`roles.ts`), HITL-Quittier-Auflösung + Sicherheits-Invariante (`acknowledge.ts`), Pipeline (`assemble.ts`).
- **Komponenten (`frontend/components/alarms/`)**: `AlarmRow` (Severity dreikanalig: Farbe+Position+Label, FCSM-Indikator, 1-Hz-Puls **nur** unquittiert-kritisch, Querlinks→B/D/E + Drift→A graceful, Handschuh-Höhe, ≥64-px-Quittier-Ziel), `AlarmBundleRow` (Flood-Bündel auf-/zuklappbar), `AcknowledgeAction` (zweistufig, Pflicht-Kontext bei kritisch, Overlay hält die Zeilenhöhe → exakte Virtualisierung), `AlarmFilterBar` (Prioritäts-Zähler + Filter + Gruppierung, atmet über den Stand-Stempel ohne Zusatz-Blinken), `AlarmList` (virtualisiert über `window.ts`, Live-Regionen höflich/assertiv), `AlarmAggregate` (Manager: nur Zähler/Trends + häufigste Quellen), `AlarmsView` (Orchestrator, Rollen-Split ohne bedingte Hooks).
- **Datenfluss**: Erstbild HTTP `GET /api/v1/alarms` über den BFF; der WS pusht **keine** Alarm-Zeilen, nur Aggregat-Signale (`overview`/`machine:{id}`) → gedrosselte Nachladung + ID-Diff für den Einblend-Puls (kein Listen-Sprung). Lebenszyklus live/gecacht folgt dem WS-Verbindungsstatus (Degradation friert ein).
- **HITL-Grenze (hart)**: Quittieren ist eine Alarm-**Status**-Aktion — **nie** Anlagen-Aktorik. `isAlarmStatusActionPath` lässt ausschließlich den `…/acknowledge`-Pfad zu (Negativtest). Reale Route nur für Drift-Warnungen (`POST /api/v1/reasoners/drift/alarms/{id}/acknowledge`).
- **Rollen (Matrix 3.1)**: Werker lesen+filtern (kein Quittieren), Schichtleiter voll (Quittieren Default, Pflicht-Kontext kritisch), Techniker zugewiesene (offline lesbar), Manager nur Aggregat. Eskalations-Verschärfung offener kritischer Alarme in die `GlobalStatusBar` (assertiv, Sprung zur Sicht).
- **Markierte Anschlusspunkte (bewusst, nicht erfunden)**: (1) **generische Quittier-Route** für Nicht-Drift-Alarme fehlt im Backend → `AcknowledgeAction` zeigt für diese Klasse einen deaktivierten, begründeten Zustand. (2) **`GET /api/v1/alarms` ist server-seitig nicht scope-gefiltert** → der Rollen-Scope ist ein **UX-Filter**, keine AuthZ-Grenze (Sichtbarkeit ≤ Backend, da das Backend alles zurückgibt); echte Scope-Filterung der Liste gehört ins Backend. (3) **Shelving/„außer Dienst"** sind im Backend nicht persistiert → Shelving ist client-seitig, sichtbar und zeitbegrenzt (15 min); „außer Dienst" ist als ISA-18.2-Zustand vorbereitet, aber ohne Backend-Signal nicht verdrahtet. (4) **Quittier-Begründung** wird client-seitig für HITL/Audit geführt; die Drift-Route nimmt keinen Body → Persistenz der Begründung gehört zu Sektion I (Audit). (5) **zeitgesteuerte Eskalation an die nächste Stufe** (Frist→Benachrichtigung) hängt an den noch offenen Eskalations-Fristen (Studie Anhang, offener Punkt 5) — die clientseitige Eskalations-Darstellung ist voll gebaut, die Benachrichtigung ist vorbereitet. (6) Maschinen-Labels für Werker/Techniker fallen ohne overview-Zugang auf „Maschine {id}" zurück.

### 21.10 Sektion E — Ausfallvorhersage & Empfehlung (F5-FE Prompt 3, [STEHT]) + geteiltes On-Demand-Muster

Zweite voll ausgebaute Sektion, unter der schärfsten der drei Haltungen: der **Simulations-Vorbehalt** ist untrennbarer Bestandteil, kein Beiwerk. Leitfrage: „Wie wahrscheinlich ist ein Ausfall, warum, was soll ich tun — und wie sehr darf ich dieser Zahl trauen?" Designgrundlage: Studie §4E (+ §1.3/§3.2/§5.2/§5.5/§5.6). Route `/insights/prediction` unter dem Erkenntnisse-Hub `/insights`.

- **Geteiltes On-Demand-Muster (`frontend/lib/ondemand/` + `frontend/components/ondemand/`)** — der wiederverwendbare Dreischritt (Studie §3.2) für E und alle späteren On-Demand-Sektionen D/F/G/H: `machine.ts` (reiner Reducer `idle → processing → result/error`, Degradation hält frühere Ergebnisse mit Stand), `use-online.ts` (Netz-Status für „offline → Trigger deaktiviert mit Grund"); Komponenten `TriggerButton` (handschuhsicher, deaktiviert-mit-Grund, keine Dringlichkeits-Animation), `NamedProcessingState` (benannter Fortschritt statt Spinner, reduced-motion), `ResultWithProvenance` (Ergebnis + `ProvenanceStamp`). „Erklärte Empfehlung" ist damit ein wiederkehrendes Muster, nicht zehn Dialoge.
- **Reine View-State-Logik (`frontend/lib/prediction/`)** — transport-agnostisch, ohne UI testbar: `confidence.ts` (verbale Stufe + grobes Band, **keine Scheingenauigkeit**; der Vertrag liefert nur einen Punktwert → es wird **keine** Bandbreite erfunden, die Vergröberung ist ehrlich markiert), `factors.ts` (Werker-Paraphrase der Feature-Tags, **Faktor-Methode unbenannt** — kein Verfahrensname sichtbar; relatives Gewicht farbunabhängig), `caveat.ts` (deterministischer Backend-Vorbehalt + **Negativ-Guard**), `decision.ts` (HITL quittieren/verwerfen mit Begründung, auditierbar; **kein Aktor-Pfad**), `view-model.ts` (führt F-PRED + F-REC zur Vier-Block-Karte zusammen; **Vorbehalt-Pflichtprüfung** + Integritäts-Guard Empfehlung↔Vorhersage), `roles.ts`, `aggregate.ts` (Manager-Risikobild), `url.ts` (reale BFF-Routen), `use-prediction.ts` (On-Demand-Anbindung).
- **Komponenten (`frontend/components/prediction/`)**: `ConfidenceCaveatCard` (das Herzstück — **vier Blöcke in fester Reihenfolge** Konfidenz → Einflussfaktoren → Empfehlung → Vorbehalt, in **einem gemeinsamen Rahmen**; der Vorbehalt sitzt im selben `<article>` wie die Konfidenz, ist **nie wegklappbar** — man sieht die Zahl nie ohne den Vorbehalt), `ConfidenceBand` (eine ruhige Farbe, Band + verbale Stufe + Vorlauf-Horizont, Schwellwert markiert), `InfluenceFactorList` (Pfeil+Wort für Richtung, Balken+Wort für Gewicht — farbunabhängig; Werker knapp, Techniker Detail), `RecommendationBlock` (Empfehlung **immer als Vorschlag**, nie Befehl), `CaveatBlock` (note/caveat, festes Symbol, deterministischer Text, defensive Zweitlinie), `DecisionAction` (zweistufig, Begründungs-Pflicht, „Anlage wird nicht geschaltet"), `PredictionView/Panel/Aggregate` (Rollen-Split ohne bedingte Hooks), `cross-links.tsx` (graceful Kontextnavigation).
- **Datenfluss**: On-Demand über den BFF. Trigger (Schichtleiter) `POST /api/v1/reasoners/failure/predict` → `POST …/predictions/{id}/recommendation`. Autoload (Werker/Techniker) lädt die jüngste **vollständige** Erkenntnis (Vorhersage **+** Empfehlung) als Snapshot — **nie eine nackte Vorhersage**. Ergebnis als „gecacht, Stand X" (On-Demand = Momentaufnahme, kein Live-Puls).
- **Vorbehalt untrennbar (Kern)**: Block 4 zeigt den **deterministischen** `validation_caveat` aus F-REC (DB-CHECK-erzwungen, wörtlich, nie im Frontend formuliert). **Negativ-Guard**: fehlt der `validation_caveat` (oder ist leer), wird **keine** Karte gerendert, sondern der Fehler-Zustand (`view-model.assemblePredictionCard` + Komponenten-Zweitlinie) — eine Vorhersage ohne ihren Vorbehalt erreicht den Schirm nie.
- **HITL-Grenze (hart)**: die Empfehlung ist ein **Vorschlag**, nie ein Befehl, nie mit einer Schalt-Aktion verknüpft. Quittieren/Verwerfen ist eine menschliche, auditierbare Entscheidung (wer/wann/warum) — **client-seitig** geführt (es gibt **keine** Backend-Entscheidungs-Route), vorbereitet für Audit (I). `predictionDecisionEndpoint()` ist `null`; `isPredictionAuditActionPath` lässt nur einen künftigen Audit-Append-Pfad zu, **nie** einen Aktor-Pfad (Negativtest).
- **Rollen (Matrix 3.1)**: Werker liest Empfehlung + Vorbehalt knapp (kein Trigger); Schichtleiter fordert an und quittiert; Techniker liest mit Faktor-Detail; Manager sieht nur das aggregierte Risikobild, **nie die Einzelempfehlung als Befehl**. Sichtbarkeit ≤ Server-Guard (`requireSection("E")`).
- **AI-Act-Transparenz**: E ist erzeugte KI-Erkenntnis → `ProvenanceStamp` (KI-erzeugt, Stand) an jedem Ergebnis und Aggregat.
- **Markierte Anschlusspunkte (bewusst, nicht erfunden)**: (1) **keine Backend-Entscheidungs-Route** → HITL-Entscheid client-seitig + auditierbar, Persistenz gehört zu Sektion I (Audit). (2) **Backend liefert nur einen Punktwert** (`probability`), kein Unsicherheits-Band → bewusst vergröbertes Band (keine erfundene Bandbreite), die echte Unsicherheit trägt der Vorbehalt. (3) **`GET …/predictions` ist server-seitig nicht scope-gefiltert** → Rollen-Scope ist UX-Filter, keine AuthZ-Grenze (wie §21.9 C). (4) **Maschinen-Auswahl** aus `assigned_machine_ids`, Label-Fallback „Maschine {id}" — Maschinen-Liste je Linie kommt mit Sektion B. (5) **Querlinks** zu Sensorverlauf (B) und Wartung (F) sind **graceful** vorbereitet (Ziele/Anker existieren noch nicht). (6) Empfehlung wird nach der Vorhersage **automatisch nachgezogen** (kein Zwischenzustand mit nackter Zahl).

### 21.11 Sektion B — Maschinen-Detail (F5-FE Prompt 4, [KERN STEHT])

Erste [KERN]-Sektion auf dem FE1-Fundament — die zentrale Drill-down-Sicht und Ziel vieler Querlinks (C→Maschine, E→Sensorbeleg, A→Drift, H→Treffer). Leitfrage (Studie §4B): "Wie geht es dieser Maschine — jetzt und im Verlauf — und weicht sie von ihrem eigenen Normalverhalten ab?" Designgrundlage: Studie §4B (+ §2/§3.2/§5.4/§5.5/§5.6/§5.8). Routen: `/machines` (Übersicht/Landing Werker/Techniker) + `/machines/[id]` (Detail).

- **`TimeSeriesChart` (`frontend/components/machine/time-series-chart.tsx`)** — das Herzstück, ein maßgeschneidertes, token-getriebenes SVG. **Bewusst KEINE Charting-Lib**: hält das <100-kB-Erstbild-Ziel (§21.8), gibt volle Kontrolle über die Mehrkanal-Kodierung und ist trivial transport-agnostisch (reine Props). SVG nutzt `var(--color-*)` direkt (umgeht die Tailwind-Purge-Falle für dynamische Klassen). Die X-Achsen-Domäne setzt das gewählte Zeitfenster (`startMs`/`endMs`), NICHT die Daten → der Live-Rand wächst rein, ohne Achsen-/Layout-Sprung. Kodierung mehrkanalig (§5.8): Linie (Position, `data-series-1`) + Normalband (entsättigte Fläche `data-normalband`) + Drift-Differenzfläche (`diff-over` blau / `diff-under` orange + Schraffur-Pattern) + beschreibendes aria-Label. Drift ist ein Akzent, NIE Alarm-Rot (Beobachtung, kein Alarm). Eigenprofil-Overlay graceful: `profile_band` ist Backend-seitig reserviert/null → kein erfundener Strich (die `profile-band`-Bedingung bleibt als Anschlusspunkt stehen).
- **Reine View-State-Logik (`frontend/lib/machine/`)** — transport-agnostisch, ohne UI testbar: `trend-series.ts` (Merge historischer Pull + Live-1h-Fenster auf dem `bucket`-Schlüssel → sprungfrei; Drift-Segment-Ableitung gegen das Normalband), `geometry.ts` (lineare Skalen + Pfad-Bau), `time-window.ts` (Schicht 8 h / Tag 24 h / Woche 168 h; Monat/9 Monate = [VISION], die Backend-Trend-Route deckelt bei 168 h), `history.ts` (Wartung + Notizen vereint, jüngste zuerst, PII maskiert), `roles.ts` (Rollen-Varianten), `url.ts` (reale BFF-Routen), `use-machine-trend.ts` (Pull `/machines/{id}/trend` by NAME + WS `trend:{data_point_id}` by ID → eine Reihe, fünf Zustände, Degradation friert ein), `use-machine-history.ts` (blätterbarer Pull). Geteilte PII-Primitive `frontend/lib/ui/pii.ts` (`maskPseudonym` → `#hex6`; die alarm-spezifische `maskAcknowledgedBy` kann später hierauf delegieren — Naht offen).
- **Komponenten (`frontend/components/machine/`)**: `MachineHeader` (Identität + FCSM groß via `StatusIndicator size="l"`, live über `machine:{id}`, + KPI + Schnellaktionen), `MachineSpecs` (Stammdaten), `MachineHistory` (chronologisch, blätterbar, PII maskiert), `MachineAlarms` (offene Alarme über die WIEDERVERWENDETE C-`AlarmRow` + `buildAlarmViewModel`, client-seitig maschinengefiltert — KEIN dupliziertes Alarm-Rendering), `MachineList` (`/machines`), `MachineCrossLinks` (Notiz → J, Vorhersage → E, Ereigniskette → D als Navigation/Anforderung), `SensorPicker`/`TimeWindowPicker`, `MachineDetailView` (Orchestrator, Rollen-Split OHNE bedingte Hooks).
- **Datenfluss**: Stammdaten/Komponenten/Datenpunkte als SSR-Pull (Erstbild) über die Detail-Route; der Sensortrend kombiniert historischen Pull mit dem Live-Thema `trend:{data_point_id}` (das bei jedem Reading das GANZE 1-h-Fenster neu pusht → Merge auf `bucket`); Historie/Alarme als Pull über den BFF.
- **HITL-Grenze (hart)**: keine Anlagen-Aktorik. Die Schnellaktionen sind Navigation/Anforderung; Quittieren ist eine Alarm-Status-Aktion über die eingebettete C-`AlarmRow` (reale Quittier-Route nur für Drift).
- **Rollen (Matrix 3.1, `ACCESS_MATRIX.B` = worker reduced / shift_lead full / technician full / manager reduced)**: Werker liest + erfasst Notiz, reduzierte Sensorauswahl; Schichtleiter voll, fordert Vorhersage an, quittiert; Techniker volle Dichte + Diagnose-Tiefe + Offline-Cache; Manager verdichtet, keine Einzelaktion. Sichtbarkeit ≤ Server-Guard (`requireSection("B")`).
- **PII (§8)**: `performed_by`/`author`/`acknowledged_by` als `#hex6` maskiert (`maskPseudonym`); `worker_notes.text` ist backend-seitig bereits NER-maskiert (durchgereicht); `maintenance_events.description` ist Sach-/SPS-Text (unmaskiert, dokumentiertes Restrisiko).
- **Markierte Anschlusspunkte (bewusst, nicht erfunden)**: (1) F4-Eigenprofil-Overlay (`profile_band` reserviert/null) → graceful weggelassen; (2) tiefe Zeitreise (Scrubbing, Monat/9 Monate, Profil-/Klassenvergleich) = [VISION], die Komponente ist erweiterbar entworfen; (3) GET `/machines`, `/alarms` und der Trend sind server-seitig NICHT scope-gefiltert → der Rollen-Scope ist ein UX-Filter; die echte AuthZ-Grenze hält das Backend auf den WS-/Trend-Themen (§20.4) — fremde Maschine → die Trend-/Alarm-Panels zeigen den Forbidden-Zustand; (4) kein Einzelmaschinen-HTTP-Status für Werker/Techniker → der FCSM-Status kommt über den `machine:{id}`-WS-Snapshot; (5) Querlinks J/D graceful (Platzhalter-Ziele).
- **Gates** (lokal grün): tsc strict 0, ESLint 0, Vitest 301 gesamt (58 neu für B), tokens:check synchron, `next build` ok (`/machines/[id]` ~121 kB First Load — bespoke SVG ohne Charting-Lib). Hidden-Term-Scan sauber.

### 21.12 Sektion H — Gedächtnis & Verknüpfung (F5-FE Prompt 5, [KERN STEHT])

Die zweite [KERN]-Sektion und FOREMANs Alleinstellung: die Bedeutungssuche "hatten wir das schon mal — irgendwo, an irgendeiner Maschine, in irgendeiner Schicht?" (Studie §4H). Eigener, begehbarer Raum (`/memory`) UND von überall über die Befehlsleiste erreichbar (Cmd-K → H). Designgrundlage: Studie §4H (+ §3.2 On-Demand, §3.3 CommandPalette, §5.5, §5.8). **Schärfstes Hidden-Term-Gate der Serie** — die Fähigkeit erscheint ausschließlich in Hallensprache; kein interner Verfahrens-/Bibliotheks-/Substrat-Begriff im sichtbaren UI (eigener Test `frontend/components/memory/hidden-term.test.tsx`).

- **Reine View-State-Logik (`frontend/lib/memory/`)** — transport-agnostisch, ohne UI testbar: `view-model.ts` (`assembleSearchResult`: F-SEM-Antwort → sortierte Trefferliste; bewahrt die Backend-Reihenfolge als Rang = Relevanz-Signal; Autor maskiert via `lib/ui/pii.ts` → `#hex6`; Auflösung graceful null), `relevance.ts` (`strengthFromRank`: ordinale Nähe-Stufe aus der Position — NIEMALS Prozent, das Backend liefert keinen Score), `cluster.ts` (Verdichtung über gleiche Maschine, `sharedResolution` graceful null), `relations.ts` (Verknüpfung NUR aus realen Feldern: gleiche Maschine/Schicht/zeitliche Nähe; Klasse/Wurzelursache reserviert), `excerpt.ts`, `time.ts` (relative Hallensprache, injizierbares "jetzt"), `roles.ts`, `url.ts` (reale BFF-Route `/api/v1/worker_notes/search`), `use-memory-search.ts` (On-Demand-Hook: geteilter Reducer aus `lib/ondemand/` + AbortController + sessionStorage-Cache für Offline).
- **Komponenten (`frontend/components/memory/`)**: `MemoryView` (Orchestrator, Rollen-Split + On-Demand-Phasen ohne bedingte Hooks), `MemorySearchBar` (natürlichsprachlich, prominent, optionaler Maschinen-Filter, offline deaktiviert mit Grund), `MemoryResultList` (Sortierung + Verdichtung + Verknüpfung + höfliche Live-Region mit Parity-Suffix), `SearchResultCard` (Quelle formcodiert, `RelevanceMark`, maskierter Auszug + Autor, Querlinks B/D graceful), `ResultCluster` (aufklappbare Verdichtung), `RelationView` (kompakte Beziehungsdarstellung, KEIN Graph), `SourceGlyph`, `RelevanceMark`. Befehlsleisten-Anbindung in `components/shell/command-palette.tsx` (Eingabe → `/memory?q=…`).
- **On-Demand-Wiederverwendung (aus E, nichts dupliziert)**: derselbe Reducer (`lib/ondemand/machine.ts`), `useOnline`, `NamedProcessingState` ("suche nach ähnlichen Fällen …" statt generischem Spinner), `ResultWithProvenance`.
- **Herkunft EHRLICH**: die Suche ist Abruf echter vergangener Notizen, KEINE Generierung → `ProvenanceStamp` trägt `aiGenerated=false` und keinen Vorbehalt (analog zur ehrlichen KI/Nicht-KI-Trennung). Käme später eine generative Treffer-Zusammenfassung dazu (NICHT im aktuellen F-SEM-Scope), würde DIESE als KI gekennzeichnet — hier nicht.
- **HITL-Grenze (hart)**: H zeigt und navigiert — keine Aktorik. Querlinks: Treffer → B (`/machines/{id}`, existiert), → D (Ereigniskette, folgt → graceful, kein toter Link).
- **Rollen (Matrix 3.1, `ACCESS_MATRIX.H` = worker full / shift_lead full / technician full / manager reduced)**: Werker einfache Suche + große Karten; Schichtleiter/Techniker volle Filter + Verknüpfung + Sprung in Diagnose; Manager Muster zuerst (Verdichtung), Einzelfälle eingeklappt. Sichtbarkeit ≤ Server-Guard (`requireSection("H")`).
- **PII (§8)**: der Auszug ist backend-seitig bereits NER-maskiert (durchgereicht, nie entmaskiert); der Autor erscheint nur als `#hex6` (`maskPseudonym`), nie als Klartext.
- **Markierte Anschlusspunkte (bewusst, nicht erfunden — der F-SEM-Vertrag ist dünner als die Vision)**: (1) Backend liefert KEINEN Ähnlichkeitsscore → Relevanz = Position + ordinale Stufe, keine Prozent; (2) F-SEM durchsucht NUR `worker_notes` (keine Ereignisse/Wartung/Ketten) → Quelltyp heterogen angelegt, real nur "Schichtnotiz"; (3) keine Ähnlichkeitsbegründung im Vertrag → faktische Verknüpfung aus realen Feldern statt erfundenem "ähnlich weil"; (4) kein Auflösungs-/Klassifikationsfeld → "gelöst durch …" graceful, nicht erfunden; (5) keine Maschinenklasse in der Such-Antwort → Schwestermaschinen-/Wurzelursachen-Verknüpfung reserviert ([VISION]); (6) `GET /worker_notes/search` server-seitig NICHT scope-gefiltert → Rollen-Scope ist UX-Filter, keine AuthZ-Grenze (wie §21.9/§21.10); (7) tiefere Graph-Visualisierung der Verknüpfung = [VISION]; (8) Offline: letzte Suche gecacht (sessionStorage) mit Stand, neue Suche deaktiviert mit Grund; (9) 503 bei Such-Backend-Ausfall ehrlich benannt.

### 21.13 Sektion J — Eingabe & Erfassung (F5-FE Prompt 6, [KERN STEHT])

Die dritte [KERN]-Sektion und der Werker-Input-Kanal — die Quelle des Gedächtnisses: was hier erfasst wird, taucht in B (Historie), D (Ketten) und H (Suche) wieder auf. Leitfrage (Studie §4J): „Wie bekomme ich, was ich gerade sehe, in unter 15 Sekunden korrekt zugeordnet ins System?" Erreichbar über die persistente Schnellaktion (`QuickCaptureFab`) von überall und aus B/Alarm mit Maschinen-Kontext. Designgrundlage: Studie §4J (+ §3.3 `QuickCaptureFab`, §5.4 Touch/Dichte, §5.5 `CaptureForm`/`VoiceCapture`, §5.8 A11y). Text-Erfassung = [CRUD STEHT] voll; Sprach-Eingabe = [VISION].

- **Reine View-State-Logik (`frontend/lib/capture/`)** — transport-agnostisch, ohne UI testbar: `submit.ts` (`buildNotePayload` → realer POST-Body, leere optionale Felder weggelassen; `classifyStatus` trennt hart/transient; `isSubmittable`; `submitNote` kapselt den fetch, wirft nie), `outbox.ts` (Offline-Schreib-Queue über `localStorage` unter `foreman.notes.outbox`; `enqueueNote`/`removeFromOutbox`/`readOutbox` — Storage injizierbar; **Lösch-nach-Senden** als Datenschutz-Hebel), `sync.ts` (`deriveSyncState` + `syncStatusText`, Hallensprache, „wartet auf Netz" neutral), `scope.ts` (`machineInScope`/`selectableMachines`/`isMachineSelectable` — UX-Filter), `classification.ts` (3 Kategorien mehrkanalig) + `shifts.ts` (3 Schichten), `roles.ts` (`captureRoleView`), `url.ts` (`createNoteEndpoint` → `POST /api/v1/worker_notes`). Hooks: `use-create-note` (online → POST, offline/transient → puffern, hart → melden), `use-outbox` (Flush beim Netz-Übergang, reentry-geschützt), `use-machines` (Pull + Scope-Filter, fünf Zustände), `use-context-suggestions` (dezente H-Brücke, debounced, abortbar, OHNE sessionStorage).
- **Komponenten (`frontend/components/capture/`)**: `CaptureForm` (einspaltig: Freitext ZUERST, vorbefüllte Zuordnungs-Chips Maschine/Schicht, `CategoryButtons`, großer Speichern-Button ≥ 64 px; Sync-Status + Bestätigung mit Rückfluss-Hinweis B/H), `CategoryButtons` (große, MEHRKANALIG kodierte Buttons — Farbfläche + Glyph + Label + aria-pressed, kein Dropdown; Aktiv-Fläche `fg-on-accent` ≥ 4.5:1 in beiden Themes gemessen), `MachineSelect` (Chips, fünf Zustände), `VoiceCapturePlaceholder` ([VISION]-Zielbild, NICHT interaktiv — kein Fake-Mikrofon), `ContextSuggestions` (frühere Fälle an dieser Maschine, wegklappbar, `ProvenanceStamp` `aiGenerated=false`), `SyncStatus` (höfliche Live-Region), `CaptureView` (Orchestrator, Rollen-Split ohne bedingte Hooks). `QuickCaptureFab` (Shell) ist kontextbewusst (`captureHref`: `/machines/{id}` → `?machine=`); `AlarmRow` (C) erhielt einen additiven Querlink „Notiz" → `/capture?machine=`.
- **Datenfluss**: Erstbild sofort (Freitext nutzbar); die Maschinen-Liste lädt nebenher (`GET /api/v1/machines` über den BFF, client-scope-gefiltert). Absenden: `POST /api/v1/worker_notes` über den generischen BFF-Proxy (JWT serverseitig injiziert). Offline → lokale Queue, Flush beim `online`-Event. Route `app/(app)/capture/page.tsx` (`requireSection("J")`, liest `?machine=` wie H `?q=`).
- **HITL-Grenze (hart)**: eine Notiz erfassen ist eine menschliche **Daten-Eingabe** — der einzige Schreibpfad ist `createNoteEndpoint()` (`/api/v1/worker_notes`), NIE eine Anlagen-Aktorik (Integrationstest prüft die Ziel-URL).
- **Datenschutz (§8)**: `text`-NER-Maskierung + `author`-HMAC-Pseudonymisierung passieren serverseitig (transparent gemacht: „Namen werden vor dem Speichern automatisch geschützt"). Der Offline-Puffer hält den Klartext NUR bis zum erfolgreichen Senden (`removeFromOutbox`) — kein dauerhafter Klartext-PII-Cache, der die Maskierung umginge; kein Klartext in sessionStorage/geteilten Stores.
- **Rollen (Matrix 3.1, `ACCESS_MATRIX.J` = worker/shift_lead/technician full, manager reduced)**: Werker Kernnutzer (einfachster Pfad, Sprache zuerst angeboten), Schichtleiter/Techniker erfassen + Kontextvorschläge, Manager liest (reduzierte Ansicht ohne Formular, Verweis auf H). Sichtbarkeit ≤ Server-Guard (`requireSection("J")`).
- **Markierte Anschlusspunkte (bewusst, nicht erfunden)**: (1) **`classification`** wird mehrkanalig erfasst und im POST MITgesendet, aber das heutige `WorkerNoteCreate`-Schema nimmt das Feld nicht an und verwirft es still (DB-Spalte `worker_notes.classification` existiert, §5/§14.3/§15) → wirkt ohne Frontend-Änderung, sobald das Backend-Schema nachzieht; kein FE-Fake. (2) **`author`** wird client-seitig mit der eigenen `user_id` belegt (aus `/me`), das Backend leitet ihn NICHT aus dem JWT ab → Backend-Härtung (POST sollte `author` aus dem Token nehmen). (3) **`POST` ist server-seitig NICHT scope-gefiltert** (§20: Scope gilt nur für Lese-/WS-Abos) → die Maschinen-Auswahl ist ein UX-/Führungs-Filter aus `assigned_*`, keine AuthZ-Grenze (wie §21.9–12); eine fremde Vorauswahl wird client-seitig graceful verworfen. (4) **`created_at` setzt der Server** (tz-aware) — der Client kann ihn nicht anpassen; das „optional anpassbar" der Studie ist [VISION]. (5) **Offline-Queue in `localStorage`** (Lösch-nach-Senden); eine crash-/multi-tab-robuste Queue (IndexedDB) ist [VISION]. (6) **Spracheingabe** = [VISION] (Whisper nicht gebaut) — markiertes Zielbild, kein funktionsloses Mikrofon. (7) **automatische Klassifikation** = [VISION] — der Werker wählt manuell. (8) **Kontextvorschlag** nutzt die reale F-SEM-Suche (`GET /worker_notes/search?q&machine_id=`, Sektion H) — Abruf, keine Generierung. **OPT-IN aus Datensparsamkeit (§8):** der Entwurfstext (potenziell unmaskierter Werker-Freitext) geht NUR auf eine bewusste Geste (Button „ähnliche Notizen ansehen") als Such-Query `q` raus, NIE passiv beim Tippen; ohne sessionStorage-Cache (kein lokaler Klartext bleibt liegen). Restrisiko: die Such-Query `q` ist im Suchpfad nicht NER-maskiert (Backend §15.7: keine Notiz-Texte in Logs) — bewusst auf eine Nutzergeste begrenzt statt automatisch.
- **Gates** (lokal grün): tsc strict 0, ESLint 0, Vitest 427 gesamt (neu für J: lib/capture + components/capture + `quick-capture-fab`), tokens:check synchron, `next build` ok (`/capture` ~112 kB First Load). Hidden-Term-Scan sauber (eigener Test `components/capture/hidden-term.test.tsx`).
- **Gates** (lokal grün): tsc strict 0, ESLint 0, Vitest 350 gesamt (49 neu für H), tokens:check synchron, `next build` ok (`/memory` ~112 kB First Load). Hidden-Term-Scan sauber (eigener Test).

### 21.14 Sektion A — Flotten-Cockpit (F5-FE Prompt 7, [KERN STEHT] · föderiert/WebGL = [VISION])

Erste [VISION]-Sektion mit voll baubarem Werk-/Linien-Kern — die oberste Übersichtsebene, Landing für Manager/Schichtleiter. **Löst den FE1-Übersicht-Durchstich ab** (erweitert ihn, dupliziert nicht — `views/overview/` entfernt, die Route `/overview` rendert jetzt `CockpitView`). Leitfrage (Studie §4A): „Wo in der Flotte brennt es — und wo bahnt sich etwas an?" Designgrundlage: Studie §4A (+ §2 ISA-101-Ruhe/Konfliktreihenfolge 8→4→1→3, §3.1 Rollenmatrix, §3.2 Live/Ambient, §3.3 `ScopeBreadcrumb`, §5.1 WebGL-Grenze, §5.2 entsättigte sequenzielle Palette, §5.5 `DriftHeatmap`/`KpiTile`, §5.8 A11y).

- **Reine View-State-Logik (`frontend/lib/cockpit/`)** — transport-agnostisch, ohne UI testbar: `deviation.ts` (Zell-Kodierung aus dem realen /overview-Vertrag — da das Backend HEUTE keinen kontinuierlichen Drift-Score liefert, wird die Abweichungs-**Intensität** ehrlich aus `open_by_severity` + `status` abgeleitet: sauberer 1:1-Ladder info→1 … emergency→5, Drift-Floor 2; `criticalCount`; `cellKind` brennt/bahnt-sich-an), `matrix.ts` (Gruppierung primär nach **Maschinenklasse** × Maschine, STABILE Ordnung → Live-Update in-place ohne Sprung; markiert systematische Klassen-Drift), `kpis.ts` (Aggregate über den scope-gefilterten Satz: Verfügbarkeit/Drift/kritische Alarme; ruhige Zustands-Rampen), `history.ts` (reiner Ring-Puffer für die KPI-Sparklines + Trend — die Live-Spur DIESER Sitzung, ehrlich kein Backend-Fenster), `priority.ts` (die 3–5 dringendsten Einstiege nach ISA-18.2-Dringlichkeit mit realem Querlink-Ziel), `palette.ts` (Zell-Füllung/Schraffur-Token, `var(--color-*)`-Namen statt dynamischer Tailwind-Klassen → Purge-Falle umgangen), `flip.ts` (Kipp-Erkennung: NEU in Abweichung → einmaliger Puls; beim ersten Aufbau kein Öffnen-Blitz), `grid-nav.ts` (reine Roving-Tabindex-Logik bei variabler Spaltenzahl), `scope.ts`/`url.ts` (Föderations-Scope als Client-Filter + reale Querlink-/Scope-URLs). `palette.test.ts` **MISST** den Kontrast (nicht geraten): Palette streng monoton (sequenziell, kein Regenbogen), laute Stufen ≥ 3:1 gegen die Grundfläche, Schraffur/Diff ≥ 3:1.
- **Komponenten (`frontend/components/cockpit/`)**: `DriftHeatmap` (das Herzstück — maßgeschneidertes, token-getriebenes SVG wie B's `TimeSeriesChart`, **KEINE Charting-/Heatmap-Lib**; Zeilen = Klassen, Spalten = Maschinen; MEHRKANALIG (§5.8): Füllung = entsättigte sequenzielle Intensität (`heatmap-1..5`) + Schraffur-Pattern (Richtung, farbunabhängiger Winkel) + halo-lesbarer FCSM-Buchstabe (`paint-order`-Strich, theme-agnostisch legibel) + Position + aria-Label; **severity-frei in der Fläche**; Klick/Enter → B; **Roving-Tabindex-Tastaturnav** über das Raster; Mini-Vorschau als Live-Region; Kipp-Puls `.state-flip` einmalig, reduced-motion global), `HeatmapLegend`, `CockpitKpiRow` (drei `KpiTile` aus den Aggregaten, nie nackt — Wert+Zustand+Trend+Spark; antippbar → Drill-down C), `CockpitScopeBar` (`ScopeBreadcrumb` Flotte ▸ Klasse ▸ Linie + Mehr-Werk-Föderation als dezent markiertes **Zielbild**), `PriorityColumn` („braucht Blick jetzt", reale Querlinks, Handschuh-Höhe), `CockpitView` (Orchestrator, Rollen-Split OHNE bedingte Hooks).
- **Datenfluss**: SSR-Snapshot `GET /api/v1/overview` als Erstbild (überbrückt als „gecacht"), dann Live über das WS-Thema `overview` (der ganze `FleetOverviewOut` wird gepusht) — über den Store, transport-agnostisch. Zellen aktualisieren in-place (stabile Zeilen/Spalten → kein Layout-Sprung); `ProvenanceStamp` Live-Puls + Stand-Stempel. Fünf Pflichtzustände + Degradation: offline → gecacht, eingefroren (kein weißer Screen).
- **Geltungsbereich**: `/overview` ist bereits SERVERSEITIG scope-gefiltert (manager = alle, shift_lead = seine Linien) UND es gibt KEIN line:/class:-Live-Thema → die Klassen-/Linien-Wahl ist ein reiner CLIENT-Filter über den autorisierten Satz (kein Re-Abo, per Vertrag kein Live-Event). Föderierte Mehr-WERK-Ebene = markiertes Zielbild (Single-Tenant).
- **HITL-Grenze (hart)**: das Cockpit ZEIGT und NAVIGIERT — keine Aktorik. Querlinks real (alle Ziele existieren): Zelle → B (`/machines/{id}`), kritische Alarme → C (`/alarms`), Drift/Risiko → E (`/insights/prediction?machine=`).
- **Rollen (Matrix 3.1, `ACCESS_MATRIX.A` = worker none / shift_lead reduced / technician none / manager full)**: Werker/Techniker **kein Zugang** (`requireSection("A")` leitet auf ihr Landing); Manager Flottenbild (alle Werke/Klassen), Schichtleiter Linienbild (Daten serverseitig auf seine Linien gefiltert). Sichtbarkeit ≤ Server-Guard.
- **ISA-101-Ruhe trotz Dichte**: entsättigte Grundfläche, Severity-Farbe NUR in KPI-Zeile + Prioritätsspalte (nie in der Heatmap-Fläche), die Heatmap als einzige dominante Akzentfläche (~60 %), Normalbetrieb-Zellen treten zurück (`surface-raised`, kein Buchstabe) — nur Auffälliges sticht; kein Ampel-Mosaik. Konfliktreihenfolge 8→4→1→3.
- **Markierte Anschlusspunkte (bewusst, nicht erfunden)**: (1) **kein kontinuierlicher F4-Drift-Score** im Backend → die Zell-Intensität ist die Severity-/Status-Heuristik (ehrlich markiert; sobald F4 einen Score persistiert, ersetzt der die Heuristik ohne Komponenten-Änderung). (2) **kein line:/class:-WS-Thema** → Scope ist Client-Filter über das serverseitig gefilterte /overview (kein Re-Abo). (3) **föderierte Mehr-Werk-Aggregation** = Zielbild (Single-Tenant-Backend, kein Backend). (4) **WebGL-Heatmap** für sehr große Flotten = Zielbild (§5.1: messen, nicht raten) — bespoke SVG für den realen, kleinen Bestand gebaut. (5) **Stand-Stempel** clientseitig (kein Server-Zeitstempel im /overview-Vertrag) — bei jeder neuen Lage gesetzt, SSR-hydration-sicher. (6) **KPI-Sparkline** ist die Live-Spur dieser Sitzung (kein historisches Backend-Fenster) — ehrlich, nie nackt.
- **Adversariale Multi-Agent-Review** (Workflow, 6 Dimensionen, jeder Befund gegengeprüft): 7 Befunde, 3 bestätigt + gefixt (alle A11y; die Dimensionen ISA-101-Ruhe / Heatmap-Korrektheit / Live+Degradation / Rollen+HITL / Vertrags-Ehrlichkeit kamen sauber durch). Fixes: (a) **haloed Schraffur** (neutraler `surface-canvas`-Unterstrich → auf hellen Zellen ≥ 3:1, der gemessene 2.05:1-Befund behoben); (b) **haloed Fokusring** im Zwischenraum gegen die stabile Grundfläche (≥ 3:1); (c) **dynamische Live-Region** (kritische Zelle → `assertive`/`alert`, §5.8 höflich/assertiv je Priorität). Der haloed **FCSM-Buchstabe** (fg-primary + canvas-Strich) ist der garantierte farbunabhängige Kind-Kanal: ≥ 4:1 auf JEDER Intensität (gemessen, `palette.test.ts`).
- **CodeRabbit** (PR #29, 7 Befunde, alle abgearbeitet): Roving-Tabindex gegen Matrix-Schrumpfen geklemmt (Tab-Stop bleibt erreichbar), Verlaufsspur + Kipp-Zustand bei Scope-Wechsel zurückgesetzt, sichtbarer Tastaturfokus auf den KPI-/Prioritäts-Links (kein `outline-none`), strikte Ganzzahl-Prüfung der Linien-ID (`"3abc"`/`"2.5"` → null), Systematik-Schwelle = STRIKTE Mehrheit (50/50 zählt nicht), dedizierter `components/cockpit/hidden-term.test.tsx` (Render-Scan über sichtbaren Text + aria-Labels).
- **Gates** (lokal grün): tsc strict 0, ESLint 0, Vitest 523 gesamt (94 neu für A: `lib/cockpit` + `components/cockpit`; der abgelöste Durchstich-Test entfällt), tokens:check synchron, `next build` ok (`/overview` ~116 kB First Load — bespoke SVG ohne Charting-Lib). Hidden-Term-Scan sauber (eigener Test; sichtbares Wording paraphrasiert „Drift" → „Abweichung"; `DriftHeatmap` ist nur interner Code-Name).

### 21.15 Sektion D — Ereignisketten (F5-FE Prompt 8, [STEHT]) + F-REC-Backend-Erweiterung

Die rekonstruierte Erzählung entlang der Zeit um einen **Anker-Alarm** — belegte Ereignisse und rekonstruierte Erzählung **hart getrennt**, klassenübergreifend zu Schwestermaschinen. Erbt das geteilte On-Demand-Muster aus E direkt. Leitfrage (Studie §4D): „Was geschah rund um diesen Alarm — was ist belegt, was ist rekonstruiert?" Designgrundlage: Studie §4D (+ §0/§2 acht Prinzipien, §3.1 Zeile D, §3.2 Live/On-Demand + Pin/Persist, §3.3 Sekundärnav „Ketten", §5.2/§5.3/§5.5/§5.6/§5.8). Route `/insights/chains` unter dem Erkenntnisse-Hub, `requireSection("D")`.

- **Backend (F-REC-Erweiterung, §14.5):** `EventChain` + ehrliche `SiblingReference` werden ausgeliefert **und als eingefrorener JSONB-Snapshot persistiert** (Migration 0009: `chain_snapshot`/`siblings_snapshot`, nullable). `POST /reconstruct` + `GET /explanations/{id}` → `ReasonerExplanationDetailRead` (Superset + `chain` + `siblings`); Liste bleibt schlank; neuer `GET /explanations/{id}/siblings`. Schwester-Referenzen NUR aus realen NEXUS-Recall-Treffern (Ziele `null`, wenn nicht auflösbar; leerer Recall → leere Liste). Output-Guard unangetastet.
- **Reine View-State-Logik (`frontend/lib/event-chains/`)** — transport-agnostisch, ohne UI testbar: `types.ts` (View-Modelle, trennt BELEGT-Knoten von ERZÄHLT-Segmenten), `symbols.ts` (event_type → formcodiertes Symbol konsistent mit B + **Hidden-Term-Wording**: `drift_alarm` → „Abweichungs-Alarm", nie „Drift"), `narrative.ts` (zerlegt die Erzählung an `[source_id]`-Zitaten → Quell-Chips), `timeline.ts` (Knoten zeitlich geordnet + Anker; **`coupledHighlight` reine Kopplungs-Funktion** Knoten ↔ Erzählstelle; **`nextRovingIndex` reine Tastatur-Funktion**), `confidence.ts` (verbale Stufe gering/mittel/hoch — **NIE Prozent**), `siblings.ts` (Geschwister-Mapping, navigierbar nur mit realer Ziel-Erklärung), `view-model.ts` (`assembleChainCard`: Belegt/Erzählt-Split, `chainAvailable=false` graceful bei Altdatensätzen, defensiver Fehler-Zustand; `toSummary` Manager-Ein-Satz), `roles.ts` (Zeile D), `url.ts` (reale BFF-Routen + Querlink-Ziele), `pin.ts` (Pin-Store mit injizierbarem Storage, **eingefrorener Stand-Stempel**), `use-chains.ts` (On-Demand-Trigger, erbt den geteilten Reducer), `use-saved-chains.ts` (Liste + Detail als fünf-Zustände-`DataState`).
- **Komponenten (`frontend/components/event-chains/`)**: `TimelineNarrative` (das Herzstück — zweispaltig: LINKS `TimelineColumn` (vertikale belegte Zeitachse, **bespoke SVG-`ChainSymbol`** je Typ, Anker hervorgehoben, dezente Verbindungslinie = **zeitliche Folge, NICHT Kausalität**, Roving-Tastatur), RECHTS `NarrativePanel` (als „rekonstruiert" gekennzeichnet, Hypothese-Badge, verbale Konfidenz, **geflaggte/unbelegte Inhalte sichtbar**, Quell-Chips); **gekoppeltes Hervorheben** Knoten ↔ Chip; Anker-Leiste oben; mobil gestapelt), `ChainSymbol` (bespoke token-getriebenes SVG, KEINE Lib; Alarm/Abweichung/Notiz/Wartung/Anker form-codiert, entsättigt), `EventNode` (untrusted Notiz sichtbar als unsicher, **keine Severity-Farbe**), `SiblingChains` (klickbar nur bei realem Ziel; leer → Block erscheint nicht), `PinChainAction`, `ChainTriggerPanel` (Trigger → benannter Zustand „verknüpfe Ereignisse über die Klasse …" → Ergebnis mit Herkunftsstempel), `SavedChainsList` (fünf Zustände, jüngste zuerst), `ChainsAggregate` (Manager: ein Satz + Kennzahl), `ChainsView` (Orchestrator, Rollen-Split OHNE bedingte Hooks).
- **Datenfluss**: On-Demand über den BFF. Trigger (Schichtleiter) `POST /reconstruct {anchor_alarm_id, lookback_hours?}` → `ReasonerExplanationDetailRead`. Browse: `GET /explanations` (+ `machine_id`-Filter) → Detail `GET /explanations/{id}` (eingefrorene Kette). Ergebnis als „gecacht, Stand X" (On-Demand = Momentaufnahme). Die Erzählung ist KI-erzeugt → `ProvenanceStamp` trägt „KI-erzeugt" (anders als H/Retrieval).
- **Belegt vs. erzählt (Kern §4D)**: BELEGT = die Kettenereignisse (`trusted=true` Alarm/Wartung solide; `trusted=false` Werkernotiz sichtbar unsicherer); ERZÄHLT = der `narrative`, als „rekonstruiert" markiert, `is_hypothesis`→Hypothese, `flagged_unsupported` sichtbar, `confidence` als verbale Stufe.
- **Anker-Vertrag (hart)**: der Anker IST ein Alarm — kein freies Maschine+Fenster. Einstieg primär aus **C** (`AlarmRow`-Querlink → `/insights/chains?anchor=`) und **B** (`MachineCrossLinks` → `/insights/chains?machine=`). Die Route liest `?anchor`/`?machine`/`?explanation` server-seitig (kein `useSearchParams`).
- **Pin an B (additiv)**: gespeicherte Kette über `PinChainAction` (Techniker/Schichtleiter) in den client-seitigen Pin-Store; `components/machine/pinned-chains.tsx` (NEU) zeigt sie in B mit **eingefrorenem Stand-Stempel** + Deep-Link nach D. Änderung in B rein additiv (eine Render-Zeile + neue Komponente), bestehende B-Tests unberührt.
- **HITL-Grenze (hart)**: D liest, triggert, verknüpft, pinnt — **schaltet nie**. Pin/Trigger sind Anzeige-/Anforderungs-Aktionen, keine Aktorik.
- **Rollen (Matrix 3.1, `ACCESS_MATRIX.D` = worker reduced / shift_lead full / technician full / manager reduced)**: Schichtleiter triggert + pinnt; Techniker liest für Diagnose + pinnt; Werker liest gespeicherte Ketten; Manager verdichtete Zusammenfassung (ein Satz + Kennzahl, nie volle Erzählung). Rollen-Split ohne bedingte Hooks. Sichtbarkeit ≤ Server-Guard (`requireSection("D")`).
- **ISA-101-Ruhe**: entsättigt; **keine Severity-Farbe in der Erzählung** (Farbe nur an verlinkten Original-Alarmen in C); dezente Verbindungslinien (zeitliche Folge, **nicht** Kausalität — die ist F vorbehalten); keine animierten Fließeffekte; Bewegung nur funktional (geerbter ruhiger Verarbeitungs-Puls, reduced-motion still).
- **Drei Haltungen**: HITL (keine Aktorik); Gedächtnis paraphrasiert (Hidden-Term: „Abweichung" statt Drift, keine internen Verfahrensnamen — eigener `components/event-chains/hidden-term.test.tsx`); Vorbehalt/Ehrlichkeit (die Belegt/Hypothese-Trennung IST die D-Form).
- **Markierte Anschlusspunkte (bewusst, nicht erfunden)**: (1) `GET /explanations` ist server-seitig NICHT scope-gefiltert → Rollen-Scope/Maschinen-Filter ist UX-Filter, keine AuthZ-Grenze (wie §21.9/§21.10). (2) Schwester-Referenzen leben von dem, was der reale NEXUS-Recall liefert — ohne Treffer kein Block (kein Fake). (3) Pin client-seitig (localStorage), kein Backend-Persistenz-Pfad → Pin gehört keinem Audit (vorbereitet für I). (4) Altdatensätze ohne Snapshot (`chain=null`) zeigen die Erzählung ohne Zeitachse (graceful, kein erfundener Verlauf). (5) Kausalität bleibt Sektion F vorbehalten — D zeigt nur zeitliche Folge.
- **Adversariale Multi-Agent-Review** (Workflow, 6 Dimensionen): Befunde gegengeprüft und gefixt — Dimensionen Belegt-vs-Erzählt-Korrektheit / ISA-101-Ruhe / Live+Degradation / Rollen+HITL / Vertrags-Ehrlichkeit (inkl. „keine erfundenen Geschwister") / A11y.
- **Gates** (lokal grün): Backend pytest (event_chain 99, davon 22 neu für A1/A2; ruff clean, mypy strict 0, Migration 0009 up/down getestet, Output-Guard intakt); Frontend tsc strict 0, ESLint 0, Vitest 568 gesamt (45 neu für D), tokens:check synchron, `next build` ok (`/insights/chains` ~8.5 kB / 114 kB First Load — bespoke SVG ohne Charting-Lib). Hidden-Term-Scan sauber.

### 21.16 Sektion I — Plattform/Audit ([STEHT] · Backend + FE)

Die Plattform-/Audit-Sicht: (a) **Systemtopologie** — mit welchen Quellen/Konsumenten ist FOREMAN verbunden, was fließt woher; (b) **Audit-Trail** — wer/welches System hat wann welche Erkenntnis abgerufen oder welche HITL-Entscheidung ausgelöst (zugleich AI-Act-/Art.-50-Nachweis-Beleg, §10.5). Leitfrage (Studie §4I): „Mit welchen Drittsystemen ist die Plattform verbunden, was fließt woher, und ist jede abgerufene Erkenntnis nachvollziehbar?" Designgrundlage §4I ist **[VISION]**; dieser Backend-Teil baut die *ehrlich abgeleitete* Teilmenge, nicht das volle Multi-System-Bild. Voller Backend-Vertrag: **§22**.

- **Backend (Teil 1, steht):** Audit-Trail (`src/foreman/audit/`) + Topologie-Quelle (`src/foreman/topology/`) + die Read-APIs `GET /api/v1/audit` und `GET /api/v1/topology`. Migration `0010` (unveränderliches `audit_logs` + Append-Only-Trigger). Zwei reale Writer-Pfade: HITL-Quittierung (Drift-Reasoner-Route, atomar) und MCP-Abruf (separater Sink, Read-Invariante intakt).
- **Rollen (Studie-Matrix):** Audit nur **Manager**; Topologie **Manager** voll · **Schichtleiter** nur Verbindungsstatus (kein Audit) · **Werker/Techniker** kein Zugang.
- **HITL = keine Aktorik:** der Audit protokolliert Entscheidungen, löst keine aus.
- **FE-Ansicht (Teil 2) STEHT** (ruhige, nicht-animierte bespoke-SVG-Topologie + unveränderlich-lesende Audit-Tabelle; Rollen-Split wie oben) — voller FE-Vertrag: **§21.17**.

### 21.17 Sektion I — Plattform/Audit (F5-FE Teil 2, [STEHT])

Die Plattform-/Audit-Sicht unter `/platform` (`requireSection("I")`) auf den fertigen Read-APIs (§22): ruhiges Systemtopologie-Lagebild zuerst, unveränderlich-lesende Audit-Tabelle danach. Baut die *ehrlich abgeleitete* Teilmenge des [VISION]-Zielbilds §4I — kein erfundener Knoten, kein erfundener Live-Feed. Designgrundlage Studie §4I (+ §2 ISA-101-Ruhe, §3.1 Rollenmatrix, §5.5/§5.8).

- **Reine View-State-Logik (`frontend/lib/platform/`)** — transport-agnostisch, ohne UI testbar: `types.ts` (FE-Spiegel von `TopologyView`/`TopologyNode`/`AuditEntryRead`; datetime als ISO-String; Roh-Enums defensiv `string`), `status.ts` (mehrkanaliges Mapping Verbindungsstatus → Token+Form-Glyph+Wort und Richtung → Pfeil-**Form**; fremder/leerer Wert → ehrlich `unbekannt`/`keine`, **nie grün geraten** — bewusst **nicht** das Fcsm-`StatusIndicator`-Atom, das kein `unbekannt` kennt), `topology-view-model.ts` (`assembleTopology`: gruppiert reale Knoten nach Kategorie, `vision`-Flag hat **Vorrang** → nie als reale Verbindung; `nodeDetailChips` kuratiert Hallensprache, kein internes Vokabel), `audit-view-model.ts` (`assembleAuditRow`: `actor` → `#hex6` via `maskPseudonym`, **nie** Klartext/„aufgelöst"; `detail`-JSONB defensiv flach; Backend-Reihenfolge bleibt — jüngste zuerst), `audit-filter.ts` (Filter-State → reale Query-Params, `limit` 1..1000 geklemmt, leere Felder fallen heraus), `url.ts` (BFF-Pfade gegen den **generischen Catch-all** — kein eigener Proxy-Handler nötig), `roles.ts` (`platformRoleView`: Manager voll / Schichtleiter nur Topologie / default-deny), `use-topology.ts` (HTTP-Snapshot + manueller Refresh + `probe`-Toggle), `use-audit.ts` (gefiltert/paginiert, **nur im Manager-Zweig gemountet**).
- **Komponenten (`frontend/components/platform/`)**: `TopologyGraph` (das Herzstück — maßgeschneidertes, token-getriebenes SVG, **keine** Lib; FOREMAN-Zentrum, Eingänge links / Substrat + MCP-Grenze rechts, [VISION]-Knoten in abgesetzter **gestrichelter** Zone **ohne** Konnektor; Status mehrkanalig, Datenrichtung als Pfeil-Form, ein gestörter Konnektor klar aber ruhig markiert; `role="img"` + aria-Label, dekorative Teile `aria-hidden`; statisch → reduced-motion neutral), `TopologyNodeMark` (zugängliche Knoten-Karte; exportiert den Status-Glyph + Richtungspfeil zur Wiederverwendung im Graphen), `AuditTable`/`AuditRow` (semantische Tabelle mit caption/scope-Headern, jüngste zuerst, IDs monospace, **rein lesend** — keine Mutations-Affordance), `AuditFilters` (Filter + Seitengröße, **bewusstes Anwenden** statt Fetch-pro-Tastendruck), `PlatformView` (Orchestrator, Rollen-Split **ohne bedingte Hooks**: Manager → Tabs Topologie+Audit per Roving-Tabindex; Schichtleiter → nur Topologie, der Audit-Hook wird in seinem Zweig **nie gemountet**; Werker/Techniker → default-deny-Hinweis).
- **Datenfluss**: HTTP-Snapshot über den BFF (`GET /api/v1/topology` + `GET /api/v1/audit`). **Kein WS-Live-Feed** für Sektion I (der Backend-Status wird pro Request berechnet; der „Live-Statuswechsel" der Studie ist [VISION] ohne Push) → bewusster, **manueller Refresh**. Die Substrat-Live-Probe schreibt einen Smoke-Marker (Kosten) → `probe`-Toggle gegen das Backend-Query-Param.
- **Drei Haltungen**: HITL (die Sicht **liest nur**, schaltet nie — keine Mutation/Quittierung/Aktorik); Gedächtnis paraphrasiert (das Substrat heißt außen nur „Gedächtnis-Substrat"; eigener `hidden-term.test.tsx`-Scan über das gerenderte Chrome); Vorbehalt/Ehrlichkeit (Status nur wo messbar, `unbekannt` bleibt unbekannt, `simulation` als **intern** markiert, [VISION] markiert/nie verbunden).
- **AI-Act**: der Audit-Trail IST der Art.-50-Nachweis-Beleg; die Audit-/Topologie-Ansicht selbst ist **kein** KI-Output → trägt **keine** KI-Kennzeichnung (`ProvenanceStamp` ohne `aiGenerated`).
- **Rollen (Matrix 3.1, `ACCESS_MATRIX.I` = worker none / shift_lead reduced / technician none / manager full)**: Manager Topologie + Audit; Schichtleiter nur Topologie-Status (FE ruft `/api/v1/audit` **nie** auf → kein 403, MCP-Knoten ohne Audit-Details); Werker/Techniker → `requireSection`-Landing. Sichtbarkeit ≤ Server-Guard.
- **Markierte Anschlusspunkte (bewusst, nicht erfunden)**: (1) **kein WS-Live-Feed** → HTTP-Snapshot + manueller Refresh. (2) **Per-Client-MCP-Attribution** = [VISION] (ein geteilter Consumer) → der MCP-Knoten zeigt ehrlich **eine** Grenze, keine erfundene Client-Liste. (3) der **generische BFF-Catch-all** genügt (kein eigener audit/topology-Proxy — wie bei allen Sektionen). (4) `ACCESS_MATRIX.I` + der `/platform`-Nav-Eintrag waren bereits beim FE-Fundament angelegt → additiv nichts nötig. (5) **kein Playwright/E2E** im Repo → volle Vitest-Abdeckung (Durchstich-Konvention §21.8).
- **Adversariale Multi-Agent-Review** (Workflow, 6 Dimensionen, jeder Befund gegengeprüft): alle Dimensionen strukturell sauber (Vertrags-Ehrlichkeit / ISA-101-SVG / Rollen+HITL / Privacy+Hidden-Term / A11y / State-Edge); 3 a11y-Befunde gefixt (Pagination-`aria-live`, Pagination-Button-`aria-label`, Tab-Pfeiltasten-Test), der Rest als Konformitäts-Bestätigung oder WCAG-exempt verworfen.
- **Gates** (lokal grün): tsc strict 0, ESLint 0, Vitest 629 gesamt (59 neu für I), tokens:check synchron, `next build` ok (`/platform` ~8.3 kB / 111 kB First Load — bespoke SVG ohne Charting-Lib). Hidden-Term-Scan sauber.

---

## 22. Audit-Trail & Topologie-Quelle (I-Backend)

Plattform-/Audit-Sicht der Sektion I. Zwei Backend-Stücke + ihre Read-APIs; baut die ehrlich abgeleitete Teilmenge des [VISION]-Zielbilds §4I — kein erfundenes Multi-System-Bild.

### 22.1 Audit-Trail (`src/foreman/audit/`)

- **Schema (Migration `0010`, additiv):** `audit_logs` vom nackten Skelett zum echten Trail — Spalten siehe §5. `actor` ist immer ein **HMAC-Token** (nie Klartext, §8); `user_id` bleibt erhalten, aber ungenutzt.
- **Unveränderlichkeit (Defense-in-Depth):** DB-Trigger `trg_audit_logs_append_only` (PL/pgSQL) weist `UPDATE`/`DELETE` ab — append-only an der Persistenzgrenze, nicht nur app-seitig (Vorbild: die `failure_*`-CheckConstraints). Bewusst **kein** `TRUNCATE`-Trigger (Test-/Reset-Pfade müssen leeren können; TRUNCATE feuert keine Row-Trigger).
- **Writer (`audit/writer.py`):** ein reiner Zeilen-Bauer (`build_audit_log`) + zwei Pfade. `record(session, entry)` schreibt **in die übergebene Session** (atomar, kein eigener Commit) — für HITL. `emit_mcp_retrieval(...)` schreibt **best-effort auf eigener Session + Commit** — für MCP; schluckt jeden Fehler (loggt nur), damit ein Audit-Ausfall den Abruf nie bricht.
- **Reale Schreibpfade (zwei):**
  - **HITL:** `POST /api/v1/reasoners/drift/alarms/{id}/acknowledge` schreibt nach dem `flush` einen `hitl_acknowledge`-Eintrag (`target_kind=alarm`, `origin=dashboard`, `actor` = quittierender HMAC) **in dieselbe Transaktion** wie die Quittierung. (`alarms.py` hat bewusst keine eigene Ack-Route — die reale HITL-Entscheidung lebt an der Drift-Route, §21.9.)
  - **MCP:** der Tool-Wrapper `_measured` (mcp/tools.py) emittiert im `finally` — **nach** dem Schließen der read-only-Session — einen `mcp_retrieval`-Eintrag (`origin=mcp`, `target_kind`/`target_id`/`machine_id` aus dem Abruf, `detail` = Tool + Ergebnis). Eigene Session/Commit; die MCP-Read-Invariante (I, §17.1) bleibt intakt.
- **MCP-Akteur (ehrlich):** `mcp/auth.py` kennt **keine** Per-Client-Identität — nur einen geteilten Bearer-Token. Der `actor` ist daher ein **pseudonymisiertes Single-Consumer-Label** (`MCP_CONSUMER_LABEL`), ehrlich genau eine Konsumenten-Grenze. Per-Client-Attribution ist **[VISION]** bis es echte Per-Client-Credentials gibt.
- **Read-API:** `GET /api/v1/audit` — Filter `action_type`/`target_kind`/`target_id`/`actor`/`machine_id`/`since`/`until`, paginiert (`limit`/`offset`), jüngste zuerst, **nur Manager** (sonst 403). `actor` bleibt pseudonym (`AuditEntryRead` ohne `user_id`/Legacy-Spalten).
- **Rollen-Hinweis:** die Designstudie §4I nennt „Manager/Admin"; das FOREMAN-Rollen-Vokabular (§5) kennt **keine separate `admin`-Rolle** → die Plattform-/Audit-Sicht ist durchgesetzt für `manager`. Käme später eine echte `admin`-Rolle, wird sie additiv in `_AUDIT_ROLES`/`_FULL_ROLES` aufgenommen.

### 22.2 Topologie-Quelle (`src/foreman/topology/`)

- **Ehrlich abgeleitet, nichts erfunden:** drei reale Knoten-Klassen —
  - **Eingänge:** distinct `data_points.source` + jüngste `readings`-Aktivität je Quelle (Richtung `liefert`). `simulation` als **intern** markiert (kein externer Peer).
  - **Gedächtnis-Substrat:** Health aus einer best-effort-Live-Probe (`run_substrate_smoke`, §9; schreibt einen Smoke-Marker, per `?probe=false` abschaltbar). Richtung `beides`.
  - **F7-MCP-Grenze:** Ausgang (`liest`), Aktivität aus dem Audit-Trail (`mcp_retrieval`-Einträge — Teil A speist Teil B; ohne Audit-Einsicht/Schichtleiter wird der Trail nicht gelesen).
- **Status nur wo messbar:** `verbunden`/`gestört`/`inaktiv`; wo nicht messbar → ehrlich `unbekannt`, **nie grün geraten** (Quelle ohne jüngste `readings` → `unbekannt`; veraltet → `inaktiv`).
- **[VISION]-Kategorie:** benannte Drittsysteme (ERP, Energiemanagement, externe Simulationssoftware) erscheinen NUR in einer separaten, klar markierten `vision`-Liste — nie als verbunden.
- **Hidden-Term (§8):** das Substrat heißt nach außen „Gedächtnis-Substrat" — keine internen Vokabeln in Feldwerten/Labels.
- **Read-API:** `GET /api/v1/topology` — Manager voll; Schichtleiter **nur Verbindungsstatus** (kein Audit-Bezug → MCP-Knoten ohne Audit-Details); Werker/Techniker 403. Query: `probe`, `fresh_within_minutes`.

### 22.3 Verifikation

mypy strict 0, ruff clean. Migration `0010` up/down getestet; der Trigger blockt `UPDATE`/`DELETE` nachgewiesen (eigene ephemere DB je Lauf, eindeutiger Name). MCP-Read-Only-Invariante nachgewiesen (Tool-Pfad mutiert keine Domänendaten; der Audit-Sink committet separat). `actor` durchgängig pseudonym; kein Klartext-Personenbezug außerhalb `users`. Topologie ohne erfundene Knoten; Status ehrlich; [VISION] markiert. Hidden-Term-Scan über die neuen Außen-Strings sauber. Coverage ≥ 80 % auf `audit/`/`topology/` + den neuen Routern.
