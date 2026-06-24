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
