<!--
============================================================
 FOREMAN — deploy/README.md
 Zweck: Betrieb von FOREMAN auf dem eigenen Server — Aufbau, Konfiguration
        und Geheimnisse, Übernahme von Railway, Sicherung, Wiederherstellung,
        laufender Betrieb.
 Architektur-Einordnung: Betrieb (Schicht 0). Ergänzt docker-compose.prod.yml,
        sicherung/, systemd/ und server/ in diesem Verzeichnis. DEPLOY.md im
        Wurzelverzeichnis beschreibt den Weg über Railway.
============================================================
-->

# FOREMAN auf dem eigenen Server

Stand 29.10.2026. Die Vorführinstanz läuft unter **https://www.foreman-demo.de** auf einem
Server bei netcup (Debian 13, Docker Compose), neben NEXUS, das dort ebenfalls läuft.

Befehle auf dem Server laufen als `patric` mit `sudo -n`. Abkürzung für diese Anleitung:

```bash
alias fc='sudo docker compose -f /srv/foreman/app/deploy/docker-compose.prod.yml'
```

## 1. Aufbau

| Dienst | Adresse im Netz `foreman` | Aufgabe |
|---|---|---|
| `backend` | `172.31.0.10:8000` | FastAPI; führt beim Start `alembic upgrade head` aus |
| `live-worker` | `172.31.0.11` | schreibt jede Minute Messwerte, kein HTTP-Server |
| `frontend` | `172.31.0.12:3000` | Next.js, spricht das Backend als BFF über `http://backend:8000` |
| `timescaledb` | `172.31.0.20:5432` | `timescale/timescaledb-ha:pg16`, per Digest festgeschrieben |

- **Kein Dienst veröffentlicht einen Port.** Docker setzt seine Weiterleitung vor die Regeln
  von ufw, ein `ports:` stünde offen im Netz. Erreichbar ist nur, was Caddy weiterleitet.
- **Caddy** ist ein eigenes Compose-Projekt des Servers unter `/srv/caddy`, das alle Projekte
  teilen. Es läuft im Host-Netz und holt die TLS-Zertifikate. Dieses Repository liefert nur seine
  Site-Datei `deploy/caddy/foreman.caddy`:
  - `www.foreman-demo.de/api/v1/ws` geht an das Backend (WebSocket).
  - Alles andere unter `www.foreman-demo.de` geht an das Frontend.
  - `foreman-demo.de` leitet dauerhaft auf `www.foreman-demo.de` um.
  - Die übrige API, `/metrics` und `/readyz` erreicht nur das Frontend im Netz `foreman`.
- **Gedächtnis-Substrat:** der Mandant `substrate-foreman` auf der NEXUS-Instanz desselben
  Servers. Foreman spricht sie über ihre öffentliche Domain an (`SUBSTRATE_BASE_URL` in
  `deploy/konfig/`), wie jeder andere Klient.
- Der Adressbereich `172.31.0.0/24` ist für Foreman reserviert, NEXUS belegt `172.30.0.0/24`.
  Feste Adressen liegen unter `.128`, Einmal-Läufe (`fc run --rm …`) bekommen eine darüber.

Verzeichnisse auf dem Server:

```
/srv/foreman/app        dieses Repository auf dem ausgerollten Commit (755, root)
/srv/foreman/env        Geheimnisse (700, Dateien 600) — nie ausgeben
/srv/foreman/sicherung  taeglich/ (14 Läufe), umzug/ (700)
```

## 2. Erstaufbau

1. Verzeichnisse anlegen:
   ```bash
   sudo install -d -m 755 /srv/foreman/app
   sudo install -d -m 700 /srv/foreman/env /srv/foreman/sicherung
   ```
2. Einen Commit ausrollen, mit Zeilenenden LF (sonst wird aus `an` ein `an\r`). Aus dem
   Repository auf dem eigenen Rechner (Git Bash):
   ```bash
   git -c core.autocrlf=false -c core.eol=lf archive <commit> | ssh patric@<server> "sudo -n tar -x -C /srv/foreman/app"
   ssh patric@<server> "sudo -n grep -rlIP '\r$' /srv/foreman/app"   # muss leer bleiben
   ```
3. Prüfen, dass der Adressbereich frei ist: `ip route | grep 172.31.` bleibt leer.
4. Geheimnisse anlegen und übernehmen (§3).
5. Abbilder bauen: `fc build`. Das Backend-Abbild lädt beim Bau das spaCy-Modell und das
   Einbettungsmodell (zusammen rund 3 GB, `Dockerfile`), der erste Bau dauert entsprechend.
6. Datenbank: `fc up -d timescaledb`. Für eine Übernahme jetzt einspielen (§4). Bei einer
   Neuinstallation legt das Backend das Schema beim ersten Start selbst an.
7. Alles starten: `fc up -d`. Die Gesundheitsprüfung gibt dem Backend fünf Minuten Anlauf
   (Migrationen, Modelle laden), wie `healthcheckTimeout` auf Railway. Der Worker startet erst,
   wenn das Backend gesund ist.
8. Site-Datei an Caddy geben, prüfen, dann Caddy neu starten (Caddy läuft ohne Admin-Schnittstelle;
   eine neue Site braucht einen Neustart):
   ```bash
   sudo install -m 644 /srv/foreman/app/deploy/caddy/foreman.caddy /srv/caddy/sites/foreman.caddy
   sudo docker compose -f /srv/caddy/docker-compose.yml exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
   sudo docker compose -f /srv/caddy/docker-compose.yml restart caddy
   ```
   Eine fehlerhafte Site-Datei hielte Caddy beim Neustart an — und damit auch NEXUS. Deshalb
   immer erst `validate`.
9. DNS (macht Patric bei IONOS): `A` und `AAAA` für `foreman-demo.de` und `www.foreman-demo.de`
   auf die Adressen des Servers. Steht DNS erst nach dem Neustart, holt Caddy das Zertifikat mit
   wachsender Wartezeit nach — ein zweiter Neustart setzt sie zurück.

## 3. Konfiguration und Geheimnisse

Zwei getrennte Quellen, damit eine Geheimnisdatei keine Server-Einstellung verstellen kann:

- **`deploy/konfig/*.conf.env`** im Repository: nur Werte, die es auf dem Server anders gibt
  als auf Railway (`SUBSTRATE_BASE_URL`, `FOREMAN_API_URL`). Kein Geheimnis.
- **`/srv/foreman/env/`** auf dem Server, angelegt von `deploy/server/geheimnisse.py`:

| Datei | Inhalt | Entsteht |
|---|---|---|
| `timescaledb.env` | `POSTGRES_PASSWORD` | `geheimnisse.py anlegen` |
| `zugang.env` | `DATABASE_URL` mit demselben Passwort | `geheimnisse.py anlegen` |
| `backend.env`, `worker.env` | die übrigen Variablen der Railway-Dienste, wörtlich | `geheimnisse.py uebernehmen` |
| `pseudo.env` | `FOREMAN_PSEUDO_KEY_v<N>`, von Backend und Worker geteilt | `geheimnisse.py uebernehmen` |
| `restic.passwort`, `restic.repo` | Sicherung außer Haus | §5 |
| `healthchecks.env` | `FOREMAN_PING_URL` | §5 |

Die Listen in `geheimnisse.py` sind disjunkt zu `deploy/konfig/`
(`tests/unit/test_deploy_geheimnisse.py`). Ein Name, den das Skript nicht kennt, bricht ab,
statt still zu fehlen. Gibt es eine Datei schon, wird verglichen, nie überschrieben: Ein
zweiter Lauf ist die Prüfung gegen den Stand auf Railway.

```bash
sudo -n python3 /srv/foreman/app/deploy/server/geheimnisse.py anlegen
```

Übernehmen vom eigenen Rechner, im Verzeichnis, das mit dem Railway-Projekt verbunden ist. Die
Werte laufen nur durch die Pipe, nicht über den Bildschirm. In PowerShell über `cmd /c`, damit
die Bytes unverändert durchgehen:

```powershell
cmd /c "railway variables --service backend --json | ssh patric@<server> sudo -n python3 /srv/foreman/app/deploy/server/geheimnisse.py uebernehmen backend"
cmd /c "railway variables --service live-worker --json | ssh patric@<server> sudo -n python3 /srv/foreman/app/deploy/server/geheimnisse.py uebernehmen worker"
```

**Der Pseudonymisierungs-Schlüssel** (`pseudo.env`) liegt nur auf dem Server und in Patrics
Passwortmanager — nicht in der Sicherung außer Haus (§5, §8). Solange Railway noch läuft, steht
er dort im Dashboard (Dienst `backend`, Variables); von dort in den Passwortmanager übernehmen,
bevor Railway abgeschaltet wird.

## 4. Übernahme von Railway

Die Datenbank von Railway kommt als `pg_dump -Fc` herüber, zusammen mit `erweiterungen.txt`
(Fassungen von `timescaledb` und `timescaledb_toolkit`, je Zeile `<name> <fassung>`). Eingespielt
wird mit `deploy/umzug/einspielen.sh` auf dem Weg, den TimescaleDB für Hypertables vorschreibt:
leere Datenbank aus `template0`, beide Erweiterungen in genau der Fassung der Sicherung,
`timescaledb_pre_restore()`, `pg_restore`, `timescaledb_post_restore()`.

```bash
sudo -n bash /srv/foreman/app/deploy/umzug/einspielen.sh /srv/foreman/sicherung/umzug/foreman.dump /srv/foreman/sicherung/umzug/erweiterungen.txt
```

Das Skript gibt am Ende den Alembic-Stand und die Zeilen je Tabelle aus, für den Abgleich mit
denselben Zählungen auf Railway.

**Geprobt am 29.10.2026** mit einer Vorab-Sicherung von Railway gegen eine Wegwerf-Datenbank auf
dem Server, mit dem Abbild-Digest aus der Compose-Datei:

- `pg_restore` endete ohne Meldung nach 49 Sekunden.
- Fassungen wie auf Railway: TimescaleDB 2.28.1 und Toolkit 1.23.0. Das Abbild bringt von sich
  aus 2.29.2 und 1.25.0 mit, deshalb legt `einspielen.sh` die Datenbank neu an. pgvector 0.8.6
  liest die Daten aus 0.8.3.
- Zeilen je Tabelle gleich, bis auf `readings` und `readings_1m`. Dort kamen zwei Minuten
  Live-Daten hinzu, die zwischen Zählung und Sicherung entstanden.
- 91 Chunks mit Kompression, die drei Continuous Aggregates (`readings_1m`, `_1h`, `_1d`), neun
  Hintergrund-Jobs, Alembic-Stand `0013`.

**Umschalten**, in dieser Reihenfolge:

1. Auf dem Server laufen alle Dienste bis auf `timescaledb`, die Datenbank ist leer.
2. Railway: `live-worker` und `backend` anhalten, damit nichts mehr schreibt. Ab hier ist die
   Vorführung aus.
3. Sofort die Sicherung ziehen, die Zeilen je Tabelle zählen und `erweiterungen.txt` per Abfrage
   im Container erzeugen. Auf Railway liegt das Datenverzeichnis der TimescaleDB im flüchtigen
   Teil des Containers — die Datenbank wird bis dahin nicht neu gestartet.
4. Auf den Server übertragen, Prüfsummen vergleichen, einspielen, Zählung vergleichen.
5. `fc up -d`, dann die Nachweise:
   - `fc logs backend | grep "Substrat-Smoke beim Start"` zeigt `ok=True`.
   - `max(time)` in `readings` wächst von Minute zu Minute.
   - Eine Notiz oder Wartung erscheint als gespiegelter Eintrag (`substrate_ref` gesetzt).
6. DNS umstellen (§2, Schritt 9), Caddy neu starten. Den alten `CNAME www` auf Railway und den
   `TXT _railway-verify.www` entfernen.
7. Railway abschalten macht Patric, nach einigen ruhigen Tagen.

## 5. Sicherung und Alarm

| Unit | Wann | Was |
|---|---|---|
| `foreman-sicherung.timer` | täglich 03:15 UTC | `sichern.sh`: `pg_dump -Fc` nach `/srv/foreman/sicherung/taeglich/<stempel>/`, geprüft, 14 Läufe |
| `foreman-ausserhaus.service` | nach jeder erfolgreichen Sicherung | `ausserhaus.sh sichern`: restic auf die Hetzner Storage Box, Verzeichnis `foreman` |
| `foreman-lebenszeichen.service` | nach jedem erfolgreichen Lauf außer Haus | Ping an healthchecks.io |
| `foreman-alarm@.service` | bei jedem Fehlschlag | `/fail` an healthchecks.io mit dem Namen der Unit |
| `foreman-sicherung-probe.timer` | sonntags 04:30 UTC | neueste Sicherung in eine Wegwerf-Datenbank einspielen |
| `foreman-ausserhaus-probe.timer` | erster Samstag im Monat 05:30 UTC | neuesten Snapshot zurückholen, einspielen, ein Zwölftel der Daten lesen |

Die Zeiten liegen hinter denen von NEXUS (02:30, 04:00, 05:00 UTC). Das Lebenszeichen kommt nur,
wenn die Sicherung lokal geprüft **und** außer Haus angekommen und geprüft ist. Bleibt es aus,
alarmiert healthchecks.io selbst. Außer Haus geht der Lauf ohne `pseudo.env` und ohne die
Passwortdatei; die Probe prüft beides.

Einrichten (einmalig, als root auf dem Server):

1. restic-Repository und Konto: Die Adresse der Box steht nur auf dem Server, nicht in diesem
   öffentlichen Repository. Der SSH-Schlüssel ist der von NEXUS (`/root/.ssh/nexus_ausserhaus`):
   ```bash
   echo 'sftp:<konto>@<konto>.your-storagebox.de:foreman' | sudo -n install -m 600 /dev/stdin /srv/foreman/env/restic.repo
   sudo -n bash /srv/foreman/app/deploy/sicherung/ausserhaus.sh einrichten
   ```
2. Patric übernimmt das restic-Passwort und die Adresse in den Passwortmanager, in seiner eigenen
   PowerShell:
   ```powershell
   ssh patric@<server> "sudo -n cat /srv/foreman/env/restic.passwort /srv/foreman/env/restic.repo"
   ```
   Ohne Passwort ist die Sicherung außer Haus unlesbar.
3. Patric legt bei healthchecks.io einen Check an (Zeitraum ein Tag, wie der von NEXUS) und
   schreibt dessen URL auf den Server, ohne dass sie durch eine Sitzung läuft:
   ```powershell
   "FOREMAN_PING_URL=https://hc-ping.com/<uuid>" | ssh patric@<server> "sudo -n install -m 600 /dev/stdin /srv/foreman/env/healthchecks.env"
   ```
4. Units installieren und Timer starten:
   ```bash
   sudo -n install -m 644 /srv/foreman/app/deploy/systemd/foreman-* /etc/systemd/system/
   sudo -n systemctl daemon-reload
   sudo -n systemctl enable --now foreman-sicherung.timer foreman-sicherung-probe.timer foreman-ausserhaus-probe.timer
   ```
5. Einmal durchlaufen lassen und beide Proben fahren:
   ```bash
   sudo -n systemctl start foreman-sicherung.service       # löst außer Haus und Lebenszeichen aus
   sudo -n systemctl start foreman-sicherung-probe.service
   sudo -n systemctl start foreman-ausserhaus-probe.service
   systemctl --failed
   ```

Ohne grüne Probe gilt eine Sicherung nicht als vorhanden.

## 6. Wiederherstellung

1. Backend und Worker anhalten: `fc stop backend live-worker frontend`.
2. Die Datenbank `foreman` leeren — ein Schritt für einen Menschen, mit Blick auf das, was weg
   soll:
   ```bash
   fc exec -T timescaledb psql -X -U foreman -d postgres -c "drop database foreman with (force)"
   ```
3. Einen Lauf einspielen. `einspielen.sh` legt die Datenbank neu an und verweigert eine, in der
   noch etwas liegt:
   ```bash
   sudo -n bash /srv/foreman/app/deploy/sicherung/wiederherstellen.sh einspielen /srv/foreman/sicherung/taeglich/<stempel>
   ```
   Brach `pg_restore` ab, steht die Datenbank halb eingespielt im Wiederherstellungsmodus: wie
   Schritt 2 verwerfen und neu einspielen.
4. `fc up -d` und die Nachweise aus §4, Schritt 5.

Von außer Haus (Server neu aufgesetzt, §2 Schritte 1 und 2 durch, der SSH-Schlüssel für die Box
neu hinterlegt): Adresse und Passwort aus dem Passwortmanager nach
`/srv/foreman/env/restic.repo` und `restic.passwort`, dann `restic restore latest --host
foreman-netcup --tag foreman-taeglich --target /` mit `-o sftp.args="-F
/srv/foreman/app/deploy/sicherung/ssh_ausserhaus.conf"`. Das bringt die Läufe und die
Geheimnisdateien zurück. `pseudo.env` fehlt darin mit Absicht und kommt aus dem
Passwortmanager.

## 7. Betrieb

**Aktualisieren:**

1. Den neuen Commit wie in §2, Schritt 2 ausrollen. `tar -x` entfernt keine gelöschten Dateien,
   die müssen einzeln weg.
2. `fc build` und `fc up -d`. Die Migrationen laufen beim Start des Backends.
3. Hat sich `deploy/caddy/foreman.caddy` geändert: §2, Schritt 8.
4. Hat sich `deploy/systemd/` geändert: §5, Schritt 4.

Die Adresse des WebSockets ist ins Browser-Bundle eingebacken (Build-Argument
`NEXT_PUBLIC_FOREMAN_WS_URL` in der Compose-Datei). Eine neue Domain braucht einen neuen Bau des
Frontends.

**Token des Substrats drehen** (Ablauf und Fenster: DEPLOY.md §7.1):

1. Erst die Gegenstelle: NEXUS dreht den Token des Mandanten `substrate-foreman`.
2. Dann `SUBSTRATE_TOKEN` in `/srv/foreman/env/backend.env` **und** `worker.env` ersetzen — von
   Hand (`sudoedit`), der Wert läuft durch keine Sitzung.
3. `fc up -d --force-recreate backend live-worker`. Der Token wird nur beim Prozessstart gelesen.
4. Nachweis: `fc logs backend | grep "Substrat-Smoke beim Start"` zeigt `ok=True`.

**Beobachten:**

```bash
fc ps
fc logs --since 1h backend
systemctl list-timers 'foreman-*'
systemctl --failed
sudo journalctl -u foreman-sicherung -u foreman-ausserhaus -u 'foreman-alarm@*' -n 50
sudo du -sh /srv/foreman/sicherung/*
```

Nur Namen, Modus und Größe von Geheimnisdateien ansehen (`sudo ls -l /srv/foreman/env`). Nie
`cat` auf eine env-Datei, `docker inspect`, `docker compose config` oder `env` im Container —
alle vier zeigen Werte.

## 8. Datenschutz

Die Vorführinstanz verarbeitet simulierte Daten und die Konten von Vorführ-Nutzern
(`compliance/scope.yaml`, tragende Bedingung). Für den Betrieb hier gilt:

- **Dienstleister:** netcup (Server) und Hetzner (Storage Box,
  nur verschlüsselte restic-Daten; der Schlüssel liegt auf dem Server und im Passwortmanager).
  Mit dem ersten realen Werkerdatensatz sind die Verträge zur Auftragsverarbeitung mit beiden
  fällig (`compliance/scope.yaml`, offene Punkte).
- **Der Pseudonymisierungs-Schlüssel bleibt aus der Sicherung außer Haus heraus.**
  `compliance/retention-policy.yaml` macht die Sicherungsstrategie zum Teil des Löschkonzepts:
  Ein Schlüssel, der in einem Snapshot weiterlebt, wäre nicht vernichtet.
- **Offen:** Die Sicherungen enthalten die Tabelle `users` mit der Klartext-Identität. Eine
  gelöschte Zeile lebt in den lokalen Läufen bis zu 14 Tage und in den Snapshots außer Haus bis
  zum Ende ihrer Aufbewahrung (bis zu sechs Monate) weiter. Wie Löschung und Sicherung
  zusammengehen — kürzere Aufbewahrung, Löschung beim Einspielen nachziehen oder getrennte
  Sicherung von `users` —, ist nicht entschieden und gehört in `compliance/retention-policy.yaml`.
