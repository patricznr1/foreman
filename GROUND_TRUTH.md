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

| # | Reasoner | NEXUS-Fähigkeit (angebunden) |
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

*(Konkrete Routen werden hier ergänzt, sobald implementiert.)*

---

## 5. Datenbank-Schema

- Tabellen: `snake_case`.
- *(Schema wird pro Migration hier dokumentiert.)*

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
- Werker-bezogene Daten werden im Adapter-Layer anonymisiert (Strategie offen, siehe Roadmap).
