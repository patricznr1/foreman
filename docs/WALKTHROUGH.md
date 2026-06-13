# WALKTHROUGH — FOREMAN in Klartext

> **Wozu dieses Dokument?** Die `GROUND_TRUTH.md` sagt, *was gilt*. Dieses Dokument erklärt, *warum und wie* — in verständlichem Deutsch, auch für Nicht-Coder. Pro Baustein ein Abschnitt.
>
> **Spielregel:** Dieses Dokument wächst mit dem Code. Jeder Commit, der etwas baut, ergänzt hier den passenden Abschnitt — im selben Commit. So kann die Erklär-Doku nicht von der Realität abdriften.

**Stand:** 2026-06-13 · F2-Fundament gebaut (Skeleton, Schema, Migrationen, Auth, Datenschutz, Ingestion, Substrat-Smoke).

---

## Wie man dieses Dokument liest

Jeder Baustein bekommt dieselben zwei Punkte:

- **Was tut es?** — in einem Satz, ohne Fachjargon.
- **Warum existiert es / wo sitzt es?** — die Rolle in der Gesamtarchitektur.

---

## Das große Bild (in drei Sätzen)

1. Eine Produktionsanlage erzeugt ständig Messdaten und Ereignisse — FOREMAN sammelt sie ein.
2. Fünf spezialisierte "Denker" (Reasoner) werten diese Daten mit Hilfe eines Langzeitgedächtnisses aus und beantworten Fragen, die ein normales Dashboard nicht beantworten kann.
3. Die Antworten landen entweder im Werker-Dashboard oder werden über eine standardisierte Schnittstelle an andere Systeme weitergereicht.

---

## Bausteine

### Projekt-Skeleton & Tooling (`pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `postgres.conf`, `alembic.ini`)

**Was tut es?**
Definiert, womit FOREMAN gebaut und betrieben wird: Abhängigkeiten, strenge Typ-/Lint-/Test-Regeln und einen lokalen Stack aus Datenbank und App.

**Warum existiert es / wo sitzt es?**
Das Fundament der Plattform-Schicht. `pyproject.toml` legt die Qualitäts-Messlatte fest (strikte Typprüfung, Linting, mindestens 85 % Testabdeckung). `docker-compose.yml` startet die spezielle Zeitreihen-Datenbank (TimescaleDB) plus die App; `postgres.conf` stellt die Datenbank auf hohe Schreiblast ein. Passwörter kommen aus einer nicht eingecheckten Umgebungsdatei, nie aus dem Code.

### Konfiguration (`config.py`)

**Was tut es?**
Liest alle Einstellungen (Datenbank, Login-Schlüssel, Substrat-Zugang, Pseudonymisierungs-Schlüssel) aus Umgebungsvariablen an einer einzigen Stelle ein.

**Warum existiert es / wo sitzt es?**
Querschnitt der ganzen Plattform. So liegt kein Geheimnis im Code (das Repo ist öffentlich), und jede Komponente bekommt ihre Werte über denselben, getesteten Weg.

### Logging (`logging_setup.py`)

**Was tut es?**
Richtet einheitliche Log-Ausgaben mit Emoji-Präfix ein und sorgt dafür, dass keine personenbezogenen Daten in Logs landen.

**Warum existiert es / wo sitzt es?**
Grundlage der späteren Beobachtbarkeit (Latenz/Erfolg/Fehler je Aufruf). Die UTF-8-Einstellung lässt die Emoji-Logs auch auf Windows-Konsolen funktionieren.

### Datenbank-Schicht (`db/base.py`, `db/session.py`, `db/models.py`)

**Was tut es?**
Beschreibt sämtliche Tabellen als Code-Modelle und stellt die Verbindung zur Datenbank her (mit wiederverwendetem Verbindungs-Pool).

**Warum existiert es / wo sitzt es?**
Das Herzstück der Persistenz. Die Hierarchie Linie → Maschine → Komponente → Datenpunkt bildet die reale Anlage ab; Messwerte (`readings`), Alarme, Produktionsläufe, Wartungen und Schichtberichte hängen daran. Personen-Felder stehen hier nur als Token (siehe Datenschutz-Schicht), Klartext-Identität ausschließlich in `users`.

### Migrationen (`migrations/0001_initial_schema`, `migrations/0002_timescale_setup`)

**Was tut es?**
Erzeugt die Datenbank schrittweise: 0001 legt alle Tabellen an, 0002 macht `readings` zur Zeitreihen-Tabelle (Hypertable) und richtet Verdichtung, Aufbewahrung und die Vektor-Spalte ein.

**Warum existiert es / wo sitzt es?**
Damit die Datenbankstruktur nachvollziehbar und reproduzierbar wächst. 0002 setzt die Vektor-Erweiterung und fügt deshalb erst dort die `embedding`-Spalte hinzu; außerdem entstehen vorberechnete Minuten-/Stunden-/Tagesmittel, damit Dashboard und Reasoner schnell lesen und das Langzeitgedächtnis günstig bleibt.

### Auth & Zugriffsschutz (`core/security.py`, `api/auth.py`, `api/middleware.py`, `api/deps.py`)

**Was tut es?**
Registriert Nutzer mit sicher gehashten Passwörtern, gibt beim Login ein Zugangs-Token (JWT) aus und sperrt alle geschützten Routen ohne gültiges Token.

**Warum existiert es / wo sitzt es?**
Die Eingangskontrolle der Plattform. Offen sind nur Health-Check und die Login-/Registrier-Routen; alles unter `/api/v1/` braucht ein Token. Die Hilfsfunktionen (Dependencies) reichen Datenbank, Konfiguration und die Datenschutz-Werkzeuge sauber an die Endpunkte durch.

### Datenschutz-Schicht (`core/pseudonymize.py`, `core/redact.py`)

**Was tut es?**
Wandelt Werker-Kennungen in nicht umkehrbare Token um (HMAC) und entfernt Personennamen aus freien Schichtbericht-Texten (NER), jeweils bevor etwas gespeichert wird.

**Warum existiert es / wo sitzt es?**
Eingebauter Datenschutz (Privacy by Design). Die Reasoning-Schicht braucht „derselbe Werker", nicht den Namen — also speichert sie nur ein stabiles Token. Beim Freitext bleibt ein Restrisiko bestehen, deshalb wird er nie als anonym deklariert. Klartext lebt allein in `users`; ein gezielter Abgleich erlaubt die kontrollierte Rück-Auflösung für berechtigte Zwecke.

### CRUD-Router (`api/routers/{lines,machines,components,data_points,production_runs,maintenance_events,worker_notes,alarms}.py`)

**Was tut es?**
Stellt für jede Stammdaten- und Ereignis-Ressource Anlegen, Auflisten und Einzelabruf bereit.

**Warum existiert es / wo sitzt es?**
Die fachliche Oberfläche der Plattform. Bei Wartungen, Alarmen und Schichtberichten greifen die Schreibpfade automatisch die Datenschutz-Schicht: Personen-Felder werden tokenisiert, Schichtbericht-Texte maskiert.

### Ingestion (`api/routers/readings.py`)

**Was tut es?**
Nimmt ganze Mess-Pakete auf einmal entgegen und schreibt sie im schnellsten Massen-Verfahren (COPY) in die Zeitreihen-Tabelle.

**Warum existiert es / wo sitzt es?**
Der Daten-Eingang für Sensorwerte. Einzel-Inserts wären viel zu langsam; das Befüllen aus echten Protokollen (OPC UA, MQTT …) folgt in einer späteren Phase über denselben Pfad.

### Substrat-Anbindung (`substrate/client.py`, `substrate/smoke.py`, `api/routers/substrate.py`)

**Was tut es?**
Spricht das externe Gedächtnis-Substrat (NEXUS) über HTTP an und prüft beim Start sowie per Endpunkt, ob ein Merken→Abrufen-Durchlauf gelingt (`{ok, latency_ms}`).

**Warum existiert es / wo sitzt es?**
Die Brücke zum Langzeitgedächtnis. Bewusst dünn gehalten — keine internen Substrat-Mechanismen im Code. Schlägt der Test fehl, läuft die Datenaufnahme trotzdem weiter; nur das spätere Reasoning wäre eingeschränkt.

### App-Zusammenbau (`main.py`)

**Was tut es?**
Setzt die App zusammen: Logging, Auth-Middleware, alle Routen, und der Substrat-Test beim Hochfahren.

**Warum existiert es / wo sitzt es?**
Der Einstiegspunkt. Ein fehlgeschlagener Substrat-Test bricht den Start nicht ab — die Plattform bleibt verfügbar.

### Tests (`tests/`)

**Was tut es?**
Prüft jede Funktion entlang Happy-Path, Fehlerfall, Zugriffsschutz und Eingabe-Validierung — Unit-Tests ohne Datenbank, Integrationstests gegen eine echte TimescaleDB.

**Warum existiert es / wo sitzt es?**
Sichert die Qualitäts-Messlatte ab (≥ 85 % Abdeckung). Schwere Abhängigkeiten (das große Namens-Erkennungsmodell, eine echte Substrat-Instanz) werden im Test durch leichte Doppel ersetzt, damit die Prüfungen schnell und ohne große Downloads laufen.

---

### Beispiel-Schablone (zum Kopieren pro neuem Modul)

```
### <Modulname>

**Was tut es?**
…

**Warum existiert es / wo sitzt es?**
…
```
