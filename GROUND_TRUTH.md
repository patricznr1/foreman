# GROUND_TRUTH — FOREMAN

> **Single Source of Truth.** Dieses Dokument beschreibt, was *gilt* — Schema, Routen, Stack, Konventionen. Bei Widerspruch zwischen Code und diesem Dokument gewinnt zunächst dieses Dokument; danach wird eines von beiden korrigiert. Stand-Datum bei jeder Änderung aktualisieren.

**Stand:** 2026-06-12 · **Status:** Fundament-Phase (Skeleton)

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
2. **FOREMAN-Plattform** — Ingestion + fünf Reasoner + Modell-Gateway.
3. **Output-Kanäle** — Werker-Dashboard + MCP-Schnittstelle.

**Gedächtnis-Substrat:** externer Dienst hinter HTTP-API. Wird wie eine Datenbank konsumiert. **Kein Substrat-Code in diesem Repo.**

### Die fünf Reasoner

| # | Reasoner | Substrat-Fähigkeit (angebunden) |
|---|---|---|
| 1 | Ereignisketten-Rekonstruktion | zeitgefilterter Recall + Reasoning |
| 2 | Drift-Erkennung | Drift-/Stabilitäts-Überwachung |
| 3 | Ausfallvorhersage | Mustererkennung über konsolidiertem Speicher |
| 4 | Wartungszyklen-Analyse | kausale Auswertung (read-only) |
| 5 | Belastungs-Simulation | historische Grenzwerte + Hypothesen |

---

## 3. Tech-Stack (verbindlich)

- **Backend:** Python 3.12, FastAPI 0.115+, async SQLAlchemy 2.0, Pydantic v2
- **DB:** PostgreSQL + TimescaleDB + Vektor-Suche
- **Gateway:** LiteLLM — Qwen3 lokal (Ollama) + Anthropic Cloud-Fallback
- **Frontend:** Next.js 15, Tailwind, shadcn/ui, Recharts
- **Industrie:** asyncua, paho-mqtt, pymodbus
- **Integration:** MCP SDK
- **Betrieb:** Docker Compose

---

## 4. API-Konventionen

- Basis-Pfad: `/api/v1/`
- Ressourcen-Stil: `/api/v1/<resource>` (Plural, snake_case in der DB)
- Health-Check: `GET /health`
- Auth-Middleware auf allem **außer** `/auth/login`, `/auth/register`, `/health`.

### Routen (F2-Skeleton)

- `GET /health`
- `POST /auth/register`, `POST /auth/login` (JWT-Ausgabe)
- CRUD: `/api/v1/lines`, `/api/v1/machines`, `/api/v1/components`, `/api/v1/data_points`, `/api/v1/production_runs`, `/api/v1/maintenance_events`, `/api/v1/worker_notes`, `/api/v1/alarms`
- `POST /api/v1/readings` — Batch-Aufnahme von Messwerten (in F3 vom Simulation-/Protokoll-Adapter befüllt)
- `GET /api/v1/substrate/smoke` — Substrat-Round-Trip (siehe §9)

*(Reasoner-Routen werden in F4/F6 ergänzt, sobald implementiert.)*

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
- `id` PK · `machine_id` FK→machines (immer) · `component_id` FK→components (nullable) · `name` · `kind` (analog/digital/setpoint/counter) · `measurement_type` (voltage/current/dc_bus/temperature/speed/frequency/torque/force/signal/null) · `unit` (V/A/°C/rpm/Hz/Nm/N/kN/bool/…) · `source` (opcua/modbus/mqtt/s7) · `address` (Node-ID/Register) · `normal_min` · `normal_max` · `created_at`

**`readings`** — TimescaleDB-Hypertable (analoge Messwerte + digitale I/O als 0/1)
- `time` timestamptz · `data_point_id` FK→data_points · `value` double · `quality` smallint (nullable) · PK (`data_point_id`, `time`) · Hypertable auf `time`

**`alarms`** — Fehlermeldungen + Nothalt
- `id` PK · `machine_id` FK→machines · `component_id` FK (nullable) · `data_point_id` FK (nullable) · `code` · `message` · `severity` (info/warning/alarm/critical/emergency) · `category` (process/safety/hardware/electrical/…) · `raised_at` · `cleared_at` (nullable) · `acknowledged_at` (nullable) · `acknowledged_by` (pseudonymisiert: HMAC-Token über `users.id`, nullable; **Nachweis-Bezug**, auditiert re-identifizierbar für HITL/Behörde) · `created_at`
- Nothalt = `category=safety`, `severity=emergency`.

**`production_runs`** — Produktionskontext (Linien-Ebene)
- `id` PK · `line_id` FK→lines · `product_code` · `order_id` (nullable) · `batch` (nullable) · `started_at` · `ended_at` (nullable) · `created_at`

**`maintenance_events`**
- `id` PK · `machine_id` FK · `component_id` FK (nullable) · `type` · `performed_at` · `description` · `performed_by` (pseudonymisiert: HMAC-Token über `users.id`; **Nachweis-Bezug**, auditiert re-identifizierbar) · `created_at`

**`worker_notes`** — Schichtberichte (KI-Felder in F2 leer/nullable)
- `id` PK · `machine_id` FK (nullable) · `shift` · `text` · `classification` (nullable, später vom Encoder) · `embedding` (Vektor, nullable, später für semantische Suche) · `author` (pseudonymisiert: HMAC-Token über `users.id`) · `created_at`
- `text` (Freitext): Personennamen werden **vor dem Insert** per NER maskiert (Restrisiko bleibt; nie als anonym deklariert).

**`users`** — Auth
- `id` PK · `email` (unique) · `password_hash` · `role` · `created_at`

**`audit_logs`**
- `id` PK · `user_id` FK (nullable) · `action` · `target` · `created_at`

**`semantic_events`** — Spiegel der Dual-Writes ans Substrat
- `id` PK · `machine_id` FK (nullable) · `event_type` · `payload` jsonb · `substrate_ref` (nullable) · `created_at`

*(Migrationen via Alembic. Jede Migration hier kurz vermerken.)*

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
- **Trennung System of Record vs. Reasoning-Schicht:** Der rechtsverbindliche, namentliche Nachweis (Prüf-/Wartungsprotokoll, QM-System, `users`, `audit_logs`) ist attributierbar unter Art. 6 Abs. 1 lit. c (z. B. BetrSichV §14/TRBS 1203, ArbSchG §6, DGUV). FOREMAN ist **nicht** dieses System of Record für die Signatur — die Nutzdatenbank speichert nur Token; Rück-Auflösung Token→Person ist kontrolliert/auditiert und nur für berechtigte Zwecke (Auskunft/Löschung Art. 15/17, HITL-/Behörden-Nachweis).
- Klartext-Identität ausschließlich in `users`; Löschung via Crypto-Shredding (pro-Werker-Schlüssel) — Verhaltensdaten/Maschinen-Gedächtnis bleiben intakt. Löschfristen pro Feld: Nachweis-Felder (`performed_by`, `acknowledged_by`) an gesetzliche Aufbewahrungspflicht gekoppelt, `worker_notes` kürzer.
- **Human-in-the-Loop (BSI):** FOREMAN gibt Empfehlungen, aktoriert nie selbst. Safety-kritische Alarme (`category=safety`) erfordern eine Operator-Quittierung (`alarms.acknowledged_at`/`acknowledged_by`), bevor sie als erledigt gelten.

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
- **Red-Teaming (LLM01):** fester Test-Satz gegen Prompt-Injection über den `worker_notes`-Freitext-Pfad + Grounding-/Halluzinations-Check der Reasoner-Erklärungen. Teil der Test-Suite ab F4.
- **Rate-Limiting / Unbounded Consumption (LLM10):** Rate-Limit-Middleware auf der API + Token-/Timeout-/Kosten-Guard im `LLMGateway`.
- **Modell-Integrität / Supply-Chain (LLM03/04):** Modell-Versionen/Digests gepinnt (Ollama-Digest, Anthropic-Model-ID); keine ungepinnte Modell-Auflösung zur Laufzeit. FOREMAN trainiert keine Modelle — daher kein Trainingsdaten-Signatur-Apparat.

### 10.5 Compliance — EU AI Act (Phase 0, vor Code)

- Risiko-Klassifizierung dokumentiert (inkl. Art.-6(3)-Begründung).
- FOREMAN-Voreinschätzung: vermutlich *Minimal/Limited Risk*. **Aber:** Werker-Sicherheitsempfehlungen werden gegen Anhang III (Hochrisiko) geprüft.
- Transparenz: KI-generierte Empfehlungen werden als solche gekennzeichnet.
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
| Rate-Limiting + `LLMGateway`-Guards (Token/Timeout/Kosten) | F-LLM |
| Modell-Digest-Pinning | F-LLM |
| `/metrics`-Endpoint (Prometheus) | F4 |
| Red-Team-Test-Satz (Injection/Halluzination) | F4 |
| Human-in-the-Loop-Quittierung — Flow im Reasoner | F4 |
| Grafana-Dashboard | Härtung |

> **Bau-Disziplin:** Diese Maßnahmen sind als verbindliche Gates/Prinzipien dokumentiert, werden aber **pro Phase** gebaut — kein Ops-Vorbau vor dem ersten laufenden Reasoner.
