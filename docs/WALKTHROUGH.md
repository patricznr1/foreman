# WALKTHROUGH — FOREMAN in Klartext

> **Wozu dieses Dokument?** Die `GROUND_TRUTH.md` sagt, *was gilt*. Dieses Dokument erklärt, *warum und wie* — in verständlichem Deutsch, auch für Nicht-Coder. Pro Baustein ein Abschnitt.
>
> **Spielregel:** Dieses Dokument wächst mit dem Code. Jeder Commit, der etwas baut, ergänzt hier den passenden Abschnitt — im selben Commit. So kann die Erklär-Doku nicht von der Realität abdriften.

**Stand:** 2026-06-14 · F4 — Drift-Reasoner (State-Gating, Deseasonalisierung, ADWIN/river, Relevanz-Filter, HITL-Quittierung, `/metrics`; gegen die F3-Szenarien validiert) auf F3 — Datenakquise & Adapterschicht (Ingestion-COPY-Pfad, Normalformat, SourceAdapter-Interface, Simulations-Generator, best-effort Substrat-Dual-Write) und dem F2-Fundament (Skeleton, Schema, Migrationen, Auth, Datenschutz, Substrat-Smoke).

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

### Ingestion-Endpunkt (`api/routers/readings.py`)

**Was tut es?**
Nimmt ganze Mess-Pakete per HTTP entgegen und schreibt sie im schnellsten Massen-Verfahren (COPY) in die Zeitreihen-Tabelle.

**Warum existiert es / wo sitzt es?**
Der HTTP-Daten-Eingang für Sensorwerte. Er nutzt seit F3 denselben geteilten COPY-Schreibweg (`ingestion/service.py: copy_readings`) wie der Simulations-/Protokoll-Adapter — es gibt nur einen Reading-Schreibpfad, keine Einzel-Inserts.

### Internes Normalformat (`ingestion/normalized.py`)

**Was tut es?**
Definiert das einheitliche Format, das jeder Adapter ausgibt: einen normalisierten Messwert (`NormalizedReading`) und vier diskrete Ereignis-Typen (Alarm, Produktionslauf, Wartung, Werker-Notiz). Alle Zeitstempel werden auf tz-aware UTC gezwungen.

**Warum existiert es / wo sitzt es?**
Die Sprachgrenze der Datenakquise: oberhalb des Adapters weiß niemand mehr, ob die Daten aus OPC UA, MQTT oder der Simulation stammen. Das Reasoning und die DB sehen nur dieses Format.

### Adapter-Interface & Registry (`ingestion/adapter.py`, `ingestion/registry.py`)

**Was tut es?**
`SourceAdapter` ist die einzige Schnittstelle, die die Ingestion kennt — ein Adapter seedet seine Topologie und liefert (zeitlich sortiert) Readings und Events. Die Registry lädt die per Config aktiven Adapter über ihren Namen.

**Warum existiert es / wo sitzt es?**
Die Plugin-Naht der Datenakquise. Ein neuer Protokoll-Adapter wird einfach registriert, ohne dass der IngestionService geändert werden muss.

### Ingestion-Service & Dual-Write (`ingestion/service.py`, `ingestion/semantic.py`)

**Was tut es?**
Der Service konsumiert den Strom eines Adapters: Messwerte werden gebatcht und per COPY geschrieben, diskrete Ereignisse landen in ihren Tabellen. Personen-Felder laufen dabei durch die Datenschutz-Schicht (Namen maskiert, Autoren/Ausführer tokenisiert). Semantische Ereignisse werden zusätzlich best-effort ans Gedächtnis-Substrat gemeldet und in `semantic_events` gespiegelt.

**Warum existiert es / wo sitzt es?**
Das Herz der Aufnahme. Der Dual-Write ist bewusst nicht-blockierend: Fällt das Substrat aus, landen Readings und Ereignisse trotzdem vollständig in der Datenbank — nur die Referenz aufs Substrat bleibt leer und der Fehlschlag wird geloggt.

### Simulations-Adapter — Szenario & Signale (`adapters/simulation/scenario.py`, `adapters/simulation/signals.py`)

**Was tut es?**
Das Szenario-Modell liest und prüft eine YAML-Beschreibung der Anlage (Linie → Maschine → Komponente → Datenpunkt), ihrer Signal-Profile und der injizierten Drift; ungültige Szenarien werden abgelehnt. Die Signal-Generatoren erzeugen daraus Werte: Grundniveau, Schicht-Saisonalität, Rauschen — plus injizierbare Drift (Sprung, Rampe, Streuungs-Anstieg) ab einem bekannten Startzeitpunkt.

**Warum existiert es / wo sitzt es?**
Die Datengrundlage mit bekannter Wahrheit. Genau gegen diese bekannten Drift-Startpunkte wird später der Drift-Reasoner (F4) validiert; das driftfreie Szenario ist der Fehlalarm-Test.

### Simulations-Adapter — Seeding & Generator (`adapters/simulation/seed.py`, `adapters/simulation/adapter.py`)

**Was tut es?**
Das Seeding legt die im Szenario beschriebene Anlagen-Topologie idempotent an (zweimal ausführen erzeugt keine Duplikate) und merkt sich die echten Datenbank-IDs. Der Adapter verbindet Szenario, Signale und diese IDs zur normalisierten Ausgabe.

**Warum existiert es / wo sitzt es?**
Der konkrete erste Adapter. Er erfüllt das `SourceAdapter`-Interface und ist damit für den Service austauschbar gegen echte Protokoll-Adapter.

### Simulations-Runner (`adapters/simulation/runner.py`)

**Was tut es?**
Der Kommandozeilen-Einstieg mit zwei Modi: `backfill` erzeugt schnell Tage an Historie, `live` streamt im Wall-Clock-Takt für die Demo. Aufruf: `python -m foreman.adapters.simulation.runner --scenario … --mode backfill|live`.

**Warum existiert es / wo sitzt es?**
Macht die Simulation startbar — als Vordergrund-Prozess, ohne separaten Job-Worker. Backfill ist ein bewusster Sonderlauf in vergangene Zeitfenster (für F4-Validierung und Dashboard-Historie).

### Simulations-Szenarien (`adapters/simulation/scenarios/*.yaml`)

**Was tut es?**
Die mitgelieferten Szenario-Beschreibungen: realistische Verschleiß-Geschichten (Lagerschaden, Werkzeugverschleiß, Schmierstoff-Korrelation), eine gesunde Maschine ohne Drift sowie zwei schlanke Minimal-Szenarien für Tests und Demo.

**Warum existiert es / wo sitzt es?**
Die fachlich begründete (ISO-20816 u. a.) Daten-Bibliothek. Jedes Szenario trägt seine eigene „bekannte Wahrheit" (Drift-Startpunkt, Erkennungsfenster) für die spätere Reasoner-Abnahme.

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

## F4 — Drift-Reasoner (erster vollständiger Reasoner)

Der Drift-Reasoner erkennt, ob eine Maschine ihr eigenes, gewohntes Verhalten **schleichend verlässt** — nicht gegen feste Grenzwerte, sondern gegen ihr historisches Profil. Reine Algorithmik (river/ADWIN), kein KI-Sprachmodell. Sein Ergebnis ist ein **Frühwarnsignal**, keine Aktion: FOREMAN warnt, schaltet nie.

### Steady-State-Gating (`reasoners/drift/steady_state.py`)

**Was tut es?**
Entscheidet je Zeitpunkt, ob die Maschine gerade in einem vergleichbaren, ruhigen Betriebszustand läuft (Produktionslauf aktiv, Maschine an, kein Rüsten). Direkt nach einem Wechsel (Anlauf, Rüsten, Stillstand) pausiert eine Schonfrist von fünf Minuten.

**Warum existiert es / wo sitzt es?**
Der Detektor darf nicht auf dem Rohsignal laufen: ein Schichtwechsel oder ein Werkstückwechsel würde sonst fälschlich als „Drift" gemeldet. Nur stationäre Phasen werden eingespeist — außerhalb davon wird gar nichts gefüttert.

### Residuumbildung / Deseasonalisierung (`reasoners/drift/baseline.py`)

**Was tut es?**
Zieht von jedem Messwert das erwartete Profil ab — den gleitenden Median der jüngsten Werte **im selben Betriebszustand** (hier: derselben Tagesstunde) — und gibt nur die Abweichung weiter.

**Warum existiert es / wo sitzt es?**
So verschwindet die betriebliche Schwankung: Früh-, Spät- und Nachtschicht haben verschiedene mittlere Last; jede Schicht bekommt ihren eigenen Median. Ein globaler Median würde die Schichten vermengen und auf einer gesunden Maschine Fehlalarme erzeugen — der zustandsspezifische Median (Research §3) löst genau das. Übrig bleibt das eigentliche Verschleißsignal.

### Drift-Detektor (`reasoners/drift/detector.py`)

**Was tut es?**
Führt je Datenpunkt einen ADWIN-Detektor (Bibliothek `river`) auf dem Abweichungsstrom. Schlägt an, wenn sich der Mittelwert statistisch belastbar verschoben hat. Die Effektgröße wird als z-Wert (Abweichung geteilt durch die normale Streuung) gemessen — damit greift eine einheitliche Schwelle über Vibration, Drehmoment, Temperatur hinweg.

**Warum existiert es / wo sitzt es?**
ADWIN braucht keine geratene Fenstergröße und reagiert schnell auf echte Änderungen. Eine Aufwärm-Phase (100 Messpunkte) verhindert, dass ein noch unsicheres Profil schon Alarm auslöst.

### Relevanz-Filter (`reasoners/drift/relevance.py`)

**Was tut es?**
Lässt eine erkannte Verschiebung erst durch, wenn sie groß genug ist UND über mehrere Intervalle anhält.

**Warum existiert es / wo sitzt es?**
ADWIN meldet statistische Signifikanz schon sehr früh; betrieblich zählt erst eine spürbare, beständige Drift. Die Anhaltedauer trennt echte Drift (hält an) von kurzen Rausch-Ausschlägen (vergehen) — der Schlüssel zur Fehlalarm-Freiheit.

### Orchestrierung & Replay (`reasoners/drift/service.py`, `reasoners/drift/runner.py`)

**Was tut es?**
Liest das 1-Minuten-Aggregat `readings_1m`, fährt jede Maschine durch die Kette Gating → Abweichung → Detektion → Relevanz und legt bei echter Drift ein Ereignis an: eine Spiegel-Zeile in `semantic_events` (plus best-effort-Meldung ans Gedächtnis-Substrat) und eine operatorseitige Warnung in `alarms` (`category=process`, `severity=warning`). Der Runner spielt einen Zeitraum nach; vor dem Lesen wird das Aggregat aufgefrischt.

**Warum existiert es / wo sitzt es?**
Die zeitkritische Kette ist eine reine, testbare Funktion ohne Datenbank; nur das Laden/Schreiben ist drumherum. Keine Aktorik — es entsteht nur eine Warnung, die ein Mensch quittiert.

### Validierung gegen die Szenarien (`reasoners/drift/validation.py`)

**Was tut es?**
Spielt die vier Simulations-Szenarien durch den Reasoner und prüft gegen ihre eingebaute Wahrheit: Wird die injizierte Drift rechtzeitig erkannt, bleibt die gesunde Maschine ruhig?

**Warum existiert es / wo sitzt es?**
Das ist die eigentliche Abnahme. **Befund:** die Drifts (Lager, Werkzeug, Schmierung) werden zuverlässig und mit nützlichem Vorlauf **vor** dem ersten Alarm/der Werker-Notiz erkannt; die gesunde Maschine löst **keinen** Fehlalarm aus. Die sehr engen 3-Tage-Erkennungsfenster der Szenarien sind für die *progressiven* (anfangs flachen) Ramps optimistisch gesetzt — dort ist das Signal noch im Rauschen; die realistische Erkennung liegt etwas später, aber klar im betrieblich nützlichen Vorlauf (Research §7: „an Realdaten zu schärfen"). Die vollständige Herleitung der Parameter (z-Score-Schwelle, Persistenz, zustandsspezifische Baseline), die Mess-Tabellen und das Validierungs-Ergebnis stehen in [`docs/research/drift-reasoner-kalibrierung.md`](research/drift-reasoner-kalibrierung.md).

### Observability & HITL (`observability/metrics.py`, `api/metrics.py`, `reasoners/drift/router.py`)

**Was tut es?**
`GET /metrics` liefert Prometheus-Kennzahlen (Aufrufe/Latenz je Reasoner, Drift-Ereignisse, Detektionsverzug, Fehlalarme). Unter `/api/v1/reasoners/drift/` lassen sich die Warnungen auflisten und **quittieren** — eine Drift-Warnung gilt erst nach Operator-Quittierung als erledigt.

**Warum existiert es / wo sitzt es?**
Human-in-the-Loop: der Mensch bestätigt; `acknowledged_by` wird als Token abgelegt (Nachweis, nie Klartext). `/metrics` ist ohne Anmeldung erreichbar (der Mess-Sammler hat kein Login), alles andere bleibt geschützt.

---

### Beispiel-Schablone (zum Kopieren pro neuem Modul)

```
### <Modulname>

**Was tut es?**
…

**Warum existiert es / wo sitzt es?**
…
```
