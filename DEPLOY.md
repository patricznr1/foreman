<!--
============================================================
 FOREMAN — DEPLOY.md
 Zweck: Schritt-für-Schritt-Provisionierung von FOREMAN auf Railway (Etappe 1).
        Für einen Menschen folgbar (Etappe 1b). Kein Secret im Repo.
 Architektur-Einordnung: Betrieb (Railway, Schicht 0). Ergänzt railway.toml
        (Backend) + frontend/railway.toml (Frontend) um das, was config-as-code
        NICHT kann: Service-Anlage, Variablen/Secrets, Service-Referenzen.
============================================================
-->

# FOREMAN auf Railway — Deploy-Anleitung (Etappe 1)

**Ziel von Etappe 1:** FOREMAN **Backend + TimescaleDB + Frontend** online und
vorführbar. Das Gedächtnis-Substrat (NEXUS) bleibt **leer** (`SUBSTRATE_BASE_URL=""`,
Fallback) — es kommt erst in **Etappe 2** dazu. Die LLM-Reasoner laufen über die
**Anthropic-Cloud** (`cloud_only`, kein Ollama im Container).

> **Warum drei Services statt eines `railway.toml` mit drei Blöcken?**
> Railways config-as-code (`railway.toml`) ist **single-service** (nur `build`/
> `deploy`) und verwaltet **keine** Variablen. Darum:
> - `railway.toml` (Repo-Root) konfiguriert den **Backend**-Service,
> - `frontend/railway.toml` den **Frontend**-Service,
> - **TimescaleDB**, alle **Variablen/Secrets** und die **DATABASE_URL-Referenz**
>   stehen hier in dieser Anleitung (manuelle Provisionierung).

---

## 0. Vorbedingungen

- Railway-Account + ein Workspace.
- Dieses Repo bei GitHub (Railway baut bevorzugt aus dem GitHub-Repo) **oder** die
  Railway-CLI (`railway up`) für direkten Upload.
- Werkzeug zum Erzeugen von Secrets: `openssl` (für `openssl rand -hex 32`).
- Ein **Anthropic-API-Key** (für die Cloud-Reasoner).

**Reihenfolge (wichtig):** TimescaleDB → Backend → Frontend. Das Frontend braucht
beim Build die öffentliche Backend-URL (WebSocket), das Backend braucht zur Laufzeit
die DB.

> **Secrets:** Niemals ins Repo. Alle Schlüssel werden als **Railway-Variablen**
> gesetzt. Platzhalter stehen in `.env.example`.

---

## 1. Service: TimescaleDB

1. **Neuen Service** im Projekt anlegen → **Deploy from Docker Image**:
   ```
   timescale/timescaledb-ha:pg16
   ```
   (Standard-Postgres reicht **nicht** — FOREMAN braucht TimescaleDB-Hypertables +
   pgvector. Siehe `docker-compose.yml` / Research §5.)
2. **Service-Name:** `timescaledb` (auf diesen Namen beziehen sich die Referenzen unten).
3. **Variablen** des Service setzen:
   | Variable | Wert |
   | --- | --- |
   | `POSTGRES_USER` | `foreman` |
   | `POSTGRES_PASSWORD` | `openssl rand -hex 32` (oder eigenes starkes Passwort) |
   | `POSTGRES_DB` | `foreman` |
4. **Volume** anhängen, Mount-Pfad:
   ```
   /var/lib/postgresql/data
   ```
   (spiegelt `docker-compose.yml`). Sollte die Persistenz beim `-ha`-Image nicht
   greifen, den vom Image genutzten `PGDATA`-Pfad prüfen und das Volume dorthin mounten.
5. **postgres.conf-Tuning (optional):** Für die Demo genügt der Railway-Default.
   Das getunte `postgres.conf` aus dem Repo ist optional; bei Bedarf als zusätzlichen
   Config-Layer einspielen (für Etappe 1 nicht nötig).

Warten, bis der DB-Service **läuft**.

---

## 2. Service: Backend (FOREMAN-API)

1. **Neuen Service** aus **diesem GitHub-Repo** anlegen.
   - **Root Directory:** `/` (Repo-Root).
   - Railway findet `Dockerfile` + `railway.toml` automatisch
     (Builder = `DOCKERFILE`, Start-Command + Healthcheck stehen darin).
2. **Service-Name:** `backend`.
3. **Variablen** setzen (Secrets via `openssl rand -hex 32`):

   **App / Auth**
   | Variable | Wert |
   | --- | --- |
   | `ENVIRONMENT` | `production` |
   | `JWT_SECRET` | `openssl rand -hex 32` — **Pflicht** (≥ 32 Byte), sonst bricht der Start ab |
   | `JWT_ALGORITHM` | `HS256` |

   > Im `production`-Modus erzwingt FOREMAN ein sicheres `JWT_SECRET`
   > (`require_secure_secrets()` beim Start). Default/zu kurz ⇒ **kein Boot**.

   **Datenbank** — Referenz auf den TimescaleDB-Service. **`+asyncpg` ist Pflicht**
   (FOREMAN reicht die URL unverändert an den asyncpg-Treiber; Railway liefert es
   nicht automatisch):
   | Variable | Wert |
   | --- | --- |
   | `DATABASE_URL` | `postgresql+asyncpg://${{timescaledb.POSTGRES_USER}}:${{timescaledb.POSTGRES_PASSWORD}}@${{timescaledb.RAILWAY_PRIVATE_DOMAIN}}:5432/${{timescaledb.POSTGRES_DB}}` |

   > `${{timescaledb.*}}` ist Railways **Referenz-Syntax** — passt den Service-Namen
   > an, falls du den DB-Service anders genannt hast. Intern `http`/Klartext-Port
   > ist ok (Wireguard-verschlüsselt).

   **Pseudonymisierung** (HMAC; fehlt der Schlüssel, schlägt der Pseudonymizer fehl):
   | Variable | Wert |
   | --- | --- |
   | `FOREMAN_PSEUDO_KEY_VERSION` | `v1` |
   | `FOREMAN_PSEUDO_KEY_VERSIONS` | `v1` |
   | `FOREMAN_PSEUDO_KEY_v1` | `openssl rand -hex 32` (32-Byte-**Hex**) |
   | `FOREMAN_PSEUDO_TENANT` | `default` |

   **MCP-Server** (Fail-Closed; leer/zu kurz ⇒ weist alles ab):
   | Variable | Wert |
   | --- | --- |
   | `FOREMAN_MCP_TOKEN` | `openssl rand -hex 32` (≥ 32 Byte) |

   **LLM (Cloud, Anthropic)**:
   | Variable | Wert |
   | --- | --- |
   | `FOREMAN_LLM_PRIORITY` | `cloud_only` |
   | `FOREMAN_LLM_CLOUD_MODEL` | `anthropic/claude-sonnet-4-5` |
   | `FOREMAN_LLM_CLOUD_API_KEY` | `<dein Anthropic-API-Key>` |

   **Embeddings (F-SEM — in Etappe 1 optional/degradiert)**:
   | Variable | Wert |
   | --- | --- |
   | `FOREMAN_EMBED_PRIORITY` | `st_only` |

   > Ohne Ollama greift der sentence-transformers-Fallback (`BAAI/bge-m3`, CPU —
   > schwer/langsam). `st_only` spart den toten Ollama-Versuch. Semantische
   > Notiz-Suche darf in Etappe 1 degradiert sein; Dauerlast später über Ollama/GPU.

   **Substrat (NEXUS) — Etappe 2, LEER lassen**:
   | Variable | Wert |
   | --- | --- |
   | `SUBSTRATE_BASE_URL` | *(leer)* |

4. **Migrationen:** laufen **automatisch beim Start** (`alembic upgrade head` im
   `startCommand` der `railway.toml`, vor `uvicorn`). Kein separater Schritt nötig.
5. **Öffentliche Domain** generieren (Service → Settings → Networking → *Generate
   Domain*). Diese URL brauchst du gleich fürs Frontend.
6. **Verifizieren:** `https://<backend-domain>/health` → `{"status":"ok",...}`.

---

## 3. Service: Frontend (Next.js-BFF)

1. **Neuen Service** aus **demselben GitHub-Repo** anlegen.
   - **Root Directory:** `frontend`.
   - Railway findet `frontend/Dockerfile` + `frontend/railway.toml`.
2. **Service-Name:** `frontend`.
3. **Variablen** setzen:

   | Variable | Wert | Wirkung |
   | --- | --- | --- |
   | `FOREMAN_API_URL` | `http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:${{backend.PORT}}` | **server-seitig** (BFF-Proxy, `/me`, ws-ticket). **Intern** über Private Networking, `http` (verschlüsselt). |
   | `NEXT_PUBLIC_FOREMAN_WS_URL` | `wss://${{backend.RAILWAY_PUBLIC_DOMAIN}}/api/v1/ws` | **Browser** (Live-WebSocket). **Öffentlich** `wss://`. |

   > **`NEXT_PUBLIC_*` wird zur BUILD-ZEIT ins Bundle gebacken.** Diese Variable
   > **vor dem ersten FE-Build** setzen — sonst bleibt die Übersicht auf dem
   > HTTP-Erstbild (kein Live-Strom). Änderst du sie später, **neu bauen**.
   > Der Backend-Service muss seine öffentliche Domain bereits haben (Schritt 2.5),
   > damit `${{backend.RAILWAY_PUBLIC_DOMAIN}}` auflöst.

   > **Warum WS öffentlich, BFF intern?** Der HTTP-BFF-Proxy reicht **kein**
   > WebSocket-Upgrade weiter — der Browser verbindet den WS daher direkt gegen die
   > öffentliche Backend-Domain (`wss://`). Die HTTP-Calls laufen server-seitig
   > intern (kein CORS, Token bleibt im httpOnly-Cookie).

4. **Öffentliche Domain** generieren → das ist die FOREMAN-URL für den Browser.
5. **Verifizieren:** `https://<frontend-domain>/login` lädt die Login-Maske.

---

## 4. Einmal-Schritt: Park-Seed (Demo-Daten)

Die Migrationen legen nur das **Schema** an — die Demo-Daten (Twin-Park
„Montagelinie 1": 12 Maschinen, Readings, Alarme) werden **einmalig separat**
geseedet (NICHT bei jedem Boot):

```bash
# Aus dem Backend-Service-Kontext (zieht dessen DATABASE_URL):
railway run --service backend python -m foreman.adapters.simulation.park --mode backfill
```

Alternativ ein einmaliges One-off im Railway-Dashboard mit demselben Befehl.

---

## 5. Demo-Nutzer anlegen + Durchklick

```bash
# Manager-Konto registrieren (gegen die ÖFFENTLICHE Backend-Domain):
curl -X POST https://<backend-domain>/auth/register \
  -H "content-type: application/json" \
  -d '{"email":"chef@foreman.de","password":"<starkes-passwort>","role":"manager"}'
```

> Stolpersteine: `/auth/*` ist **top-level** gemountet (**nicht** `/api/v1/auth`).
> `EmailStr` lehnt reservierte TLDs wie `.local` ab → eine echte TLD (`.de`) nutzen.

Dann im Browser `https://<frontend-domain>/login` → Manager landet auf `/overview`
(Cockpit). Andere Rollen (worker/shift_lead/technician) bei Bedarf zusätzlich registrieren.

---

## 6. Verifikations-Checkliste

- [ ] `GET https://<backend-domain>/health` → `200 {"status":"ok"}`
- [ ] DB-Migrationen durchgelaufen (Backend-Logs: `alembic upgrade head` ohne Fehler)
- [ ] Park-Seed gelaufen (Maschinen/Readings/Alarme vorhanden)
- [ ] Login → `GET /api/v1/me` → `200` (Rolle = manager)
- [ ] `/overview` zeigt echte Maschinenzustände
- [ ] Live-Updates kommen (nur wenn `NEXT_PUBLIC_FOREMAN_WS_URL` zur Build-Zeit gesetzt war)

---

## 7. Etappe 2 — Substrat (NEXUS) anbinden *(Platzhalter, später)*

In Etappe 1 läuft FOREMAN bewusst **ohne** Gedächtnis-Substrat. Etappe 2 hängt es
sauber dazu:

- **Dedizierte FOREMAN-NEXUS-Instanz** (eigenes Railway-Setup, eigener Token, nur
  Industrie-Inhalte) — **nicht** gegen die persönliche Production-NEXUS (IP-/
  Datenschutz-Trennung).
- **Adapter-Fassade** vor der NEXUS, die FOREMANs generische 5 Endpunkte
  (`/remember`, `/recall`, `/reason`, `/drift_status`, `/reflect`) auf die echten
  NEXUS-Operationen übersetzt (HTTP-Methoden, SPARQL-Semantik, Auth-Schema).
- Anschließend `SUBSTRATE_BASE_URL` + `SUBSTRATE_TOKEN` am Backend setzen — die
  H-Sektion/Gedächtnis verlässt den Fallback.

Details bei Erreichen von Etappe 2.

---

## 8. Etappe 3 — Live-Daten-Stream-Worker (scharf schalten)

**Ziel:** Das Dashboard **lebt** — neue Readings ticken fortlaufend mit **aktuellen
Zeitstempeln** rein, statt dass die 21-Tage-Historie altert. Der Worker setzt den
Generator am **Ende der Backfill-Historie** an und schreibt mit Wall-Clock-Stempeln
weiter (Details/Architektur: GROUND_TRUTH §12.6). Er nutzt den **unveränderten**
Schreibpfad (COPY + NOTIFY/WS-Push) — kein zweiter Weg.

> ⚠️ **Sicherheit — Reihenfolge beachten.** Ein fehlerhafter Dauer-Schreiber auf der
> öffentlichen Live-DB ist ein Risiko. Erst der **Trockenlauf** (`--max-ticks`), Blick
> drauf, **dann** scharf (unbegrenzt). Code + Tests sind autonom gegen eine Test-DB
> verifiziert; das Scharfschalten auf Railway ist ein **bewusster manueller Schritt**.

### 8.1 Vorbedingung: Historie an „jetzt" verankern

Der Worker setzt am letzten Reading-Stempel an. Liegt der weit zurück, gibt es zwei
Wege, den Strom **ohne Aufhol-Sturm** an „jetzt" zu bringen:

**Weg A — kleine Lücke akzeptieren (nicht-destruktiv, Default):** Den Worker mit
`--max-catchup-ticks N` starten. Liegt das Historien-Ende mehr als `N` Ticks zurück,
kappt der Worker den Anker auf „jetzt − interval" (bewusste, **geloggte** Lücke statt
Boot-Storm). Die Historie bleibt **unangetastet** — der saubere Default.

**Weg B — frisches Re-Seed auf „jetzt" (destruktiv):** Den Park-Backfill mit
`--anchor-now` neu erzeugen.

> ⚠️ **`--anchor-now` ist ein *additives* Backfill, kein In-Place-Verschieben.** Es
> schreibt eine komplette neue 21-Tage-Historie mit auf „jetzt" verschobenen Stempeln.
> Auf einer **bereits geseedeten** DB entstehen dadurch **Doppeldaten** (alte + neue
> Readings mit überlappenden Stempeln) — der `readings`-Schreibpfad hat **kein**
> Truncate/Upsert. `--anchor-now` ist nur für eine **frische** DB gedacht, **oder**
> nach explizitem Leeren der Daten-Ebene (Topologie + `users` + `audit_logs` bleiben;
> `reasoner_explanations` hängt per FK an `alarms`):
>
> ```sql
> TRUNCATE readings, alarms, production_runs, maintenance_events, worker_notes,
>          reasoner_explanations, failure_predictions, failure_recommendations,
>          drift_profiles RESTART IDENTITY;
> ```
>
> Netz vor dem Truncate: `readings` ist eine TimescaleDB-Hypertable — `pg_dump -t
> readings` sichert sie **nicht** (nur die leere Parent-Hülle). Stattdessen eine
> Plain-Table-Kopie: `CREATE TABLE readings_preseed_backup AS SELECT * FROM readings;`
> (nach grünem Re-Seed wieder droppen).

```bash
# NUR auf frischer / frisch geleerter DB — sonst Doppeldaten. railway ssh (Container),
# nicht railway run (lokal): die Live-DB ist nur über Private Networking erreichbar.
railway ssh --service backend python -m foreman.adapters.simulation.park --mode backfill --anchor-now
```

### 8.2 Trockenlauf (Blick drauf, NICHT scharf)

```bash
# Begrenzter Lauf gegen die Live-DB: schreibt nur N Ticks, dann Ende.
# railway ssh (im Container) statt railway run (lokal) — railway.internal ist
# lokal nicht erreichbar; die Live-DB nur über Private Networking im Container.
railway ssh --service backend python -m foreman.adapters.simulation.live_worker --max-ticks 5 --interval-seconds 10
```

Prüfen: kommen Readings mit **aktuellen** Zeitstempeln rein (`max(time)` ≈ jetzt), ohne
Doppel (`count(*) = count(DISTINCT (data_point_id, time))`), und feuert das Dashboard-
Live-Update (`/overview` → `stream.active = true`)? Erst wenn das passt → 8.3.

### 8.3 Eigener Worker-Service (Dauerlauf)

Der Worker ist ein **eigener Railway-Service** auf demselben Repo/Image wie das
Backend — nur mit anderem Start-Command. **Kein** `alembic`, **kein** Healthcheck.

> ⚠️ **Das Root-`railway.toml` ist Backend-only** (`startCommand` = `alembic` +
> `uvicorn`, Healthcheck `/health`) und **config-as-code überschreibt** Dashboard-/
> API-Settings. Ein Worker mit Root-Directory = Repo-Root würde damit als **zweiter
> uvicorn** starten. Lösung: Der Worker-Service zeigt via **„Config-as-code file"**
> (Service-Settings; GraphQL-Feld `railwayConfigFile`) auf **`/railway.worker.toml`**
> (Start-Command `live_worker`, kein Healthcheck, Restart `ON_FAILURE`).

1. **New Service** — GitHub-Repo `foreman` **oder** „Empty Service" + `railway up`-Upload.
2. **Config-as-code file** = `/railway.worker.toml` setzen (Service-Setting). Der
   Start-Command kommt aus dieser Datei — die CLI (`railway add`/`up`) kann den
   Start-Command **nicht** direkt setzen, daher config-as-code statt Dashboard-Override.
3. **Variables** (wie Backend): `DATABASE_URL` als **Service-Referenz** auf den
   TimescaleDB-Service (`postgresql+asyncpg://${{timescaledb.POSTGRES_USER}}:…`, mit
   `+asyncpg`); `FOREMAN_PSEUDO_KEY_VERSION`/`_VERSIONS` = `v1`; `FOREMAN_PSEUDO_KEY_v1`
   am besten als **Cross-Service-Referenz** `${{backend.FOREMAN_PSEUDO_KEY_v1}}` (kein
   Secret-Kopieren, konsistente Pseudonyme). Substrat optional (`SUBSTRATE_*`, sonst
   Fallback) — der Produzent schreibt nur Readings. `JWT_SECRET` braucht der Worker
   **nicht** (er ruft `require_secure_secrets()` nie).
4. **Healthcheck**: keiner. **Restart Policy**: `ON_FAILURE` — bei Absturz/Stop
   startet Railway neu; der Worker liest den Anker **frisch aus der DB** und setzt
   ohne Doppeln/Lücke fort (neustart-fest, GROUND_TRUTH §12.6).
5. **Genau EINE** Worker-Instanz laufen lassen (`numReplicas = 1`). Zwei Schreiber auf
   demselben Grid würden um Stempel konkurrieren — der PK schützt vor Dubletten, aber
   nicht vor Reibung. Keine Replicas.

### 8.4 Verifikation (scharf)

- [ ] `8.2`-Trockenlauf grün (aktuelle Stempel, keine Doppel, Live-Update sichtbar)
- [ ] Worker-Service läuft, Logs zeigen `🔴 Live-Daten-Stream startet` + `⏱️ Live-Anker = …`
- [ ] `max(time)` der `readings` wandert mit der Wall-Clock mit (Lücke < 1 Tick)
- [ ] `/overview` → `stream.active = true`, `last_reading_at` ≈ jetzt
- [ ] Nach manuellem Restart des Service: kein Doppel (`dup = 0`), lückenlose Fortsetzung
- [ ] DB-**Historie** wie gewollt (unangetastet bei Weg A; frisch auf „jetzt" bei Weg B)
