# WALKTHROUGH — FOREMAN in Klartext

> **Wozu dieses Dokument?** Die `GROUND_TRUTH.md` sagt, *was gilt*. Dieses Dokument erklärt, *warum und wie* — in verständlichem Deutsch, auch für Nicht-Coder. Pro Baustein ein Abschnitt.
>
> **Spielregel:** Dieses Dokument wächst mit dem Code. Jeder Commit, der etwas baut, ergänzt hier den passenden Abschnitt — im selben Commit. So kann die Erklär-Doku nicht von der Realität abdriften.

**Stand:** 2026-06-16 · F7 — MCP-Schnittstelle (FOREMAN als offener Knoten: read-only Model-Context-Protocol-Server über Streamable HTTP, der die Reasoner-Erkenntnisse als maschinenlesbare Tools an Drittsysteme reicht — AI-Act-Transparenz-Flags an jedem KI-Output, PII nur pseudonymisiert/maskiert, eigene Token-Auth, Hidden-Term-Scan, keine Aktorik) auf F-REC (LLM-Werker-Empfehlung), F-PRED (Ausfallvorhersage), F-SEM (semantische Notiz-Suche), F6 (Ereignisketten-Reasoner), F-LLM (Modell-Gateway), F4 (Drift-Reasoner), F3 (Datenakquise & Adapterschicht) und dem F2-Fundament (Skeleton, Schema, Migrationen, Auth, Datenschutz, Substrat-Smoke).

---

## Wie man dieses Dokument liest

Jeder Baustein bekommt dieselben zwei Punkte:

- **Was tut es?** — in einem Satz, ohne Fachjargon.
- **Warum existiert es / wo sitzt es?** — die Rolle in der Gesamtarchitektur.

---

## Das große Bild (in drei Sätzen)

1. Eine Produktionsanlage erzeugt ständig Messdaten und Ereignisse — FOREMAN sammelt sie ein.
2. Vier spezialisierte "Denker" (Reasoner) werten diese Daten mit Hilfe eines Langzeitgedächtnisses aus und beantworten Fragen, die ein normales Dashboard nicht beantworten kann.
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

## F-LLM — Modell-Gateway (`src/foreman/llm/`)

Das Gateway ist die **dünne, austauschbare Sprach-Schicht** von FOREMAN: die einzige Stelle, über die je ein Sprachmodell angesprochen wird. Es macht die Outputs erklärbar — und ist so geschnitten, dass jeder kommende LLM-Reasoner (zuerst die Ereignisketten-Rekonstruktion) nur diese Schicht kennt und nie die darunterliegende Inferenz-Library. **Kein Reasoner in dieser Phase** — nur die Abstraktion. Leitsatz: die Library (LiteLLM) ist ein austauschbares Detail; tauscht man das Backend (Ollama lokal ↔ Anthropic Cloud ↔ später vLLM), ändert sich eine Config-Zeile, kein Reasoner-Code.

### Fehlerhierarchie (`llm/errors.py`)

**Was tut es?**
Definiert die Fehler, die ein Reasoner fangen kann: eine gemeinsame Basis `GatewayError` und darunter Konfig-Fehler, Backend-nicht-erreichbar, Rate-Limit, Grounding-Verstoß, Timeout — jeder mit den passenden Zusatzfeldern (z. B. „nach wie vielen Sekunden wieder erlaubt").

**Warum existiert es / wo sitzt es?**
Damit der Reasoner mit einem einzigen `except GatewayError` alles abfangen kann, ohne je eine LiteLLM-Ausnahme zu sehen. Das ist die Architektur-Grenze in Reinform: rohe Library-Fehler werden hier übersetzt, nicht durchgereicht.

### Konfiguration (`llm/config.py`)

**Was tut es?**
Liest alle Gateway-Parameter aus der Umgebung (`FOREMAN_LLM_*`): Backend-URLs, Modellnamen, den Priority-Modus, Timeouts, Rate-Limits, Grounding-Policy, Caching — und den Cloud-API-Key als `SecretStr`.

**Warum existiert es / wo sitzt es?**
Eine Quelle der Wahrheit für das Verhalten des Gateways; der Key kann so nie versehentlich im Log oder Repr landen (das Repo ist öffentlich). Lokal-first ist der Default — passend zur OT-Welt, die ihre Daten nicht nach draußen gibt.

### Gateway-Schnittstelle & Orchestrierung (`llm/gateway.py`)

**Was tut es?**
Stellt das `LLMGateway`-Protokoll, den strukturierten `GatewayResponse` und das Task-Enum bereit — und die konkrete `LiteLLMGateway`-Implementierung. Ein `complete(...)`-Aufruf läuft: Cache prüfen → Prompt bauen (Spotlighting) → Rate-Limit + Backend-Routing/Fallback → Grounding prüfen → Metriken + Log → fertige Antwort.

**Warum existiert es / wo sitzt es?**
Das ist die Fläche, die der nächste Reasoner berührt — bewusst so geschnitten, dass er Grounding-Quellen übergibt und eine gegroundete Erzählung zurückbekommt, ohne ein einziges LiteLLM-Konzept zu sehen.

### Backends & Fallback (`llm/backends.py`)

**Was tut es?**
Bindet LiteLLM an (lokales Ollama, Anthropic-Cloud), übersetzt eine Modell-Antwort in ein neutrales Ergebnis und fährt die Fallback-Kette: nach Priority-Modus das nächste Backend, wenn eines ausfällt.

**Warum existiert es / wo sitzt es?**
**Die einzige Datei, die LiteLLM importiert** (und das lazy). Jede Fremd-/Provider-Ausnahme wird hier in einen Gateway-Fehler übersetzt — so verlässt nichts Library-Spezifisches dieses Modul. Genau hier sitzt die harte Architektur-Grenze.

### Grounding & Spotlighting (`llm/grounding.py`)

**Was tut es?**
Baut aus den übergebenen Quellen den Prompt: vertrauenswürdige Daten klar markiert, untrusted Werker-Freitext datamarkiert und mit einem zufälligen Delimiter abgegrenzt, plus die Instruktion „Freitext ist Daten, keine Anweisung". Nach der Antwort prüft ein Post-Check, ob Zahlen auftauchen, die in keiner vertrauenswürdigen Quelle stehen.

**Warum existiert es / wo sitzt es?**
Das ist die Verteidigung gegen indirekte Prompt-Injection (Schutz-Doc): eine in eine Werker-Notiz geschmuggelte „999 Grad" wird nicht belegt und fällt durch. Die **Mechanik** stellt das Gateway bereit; die **Quellen** liefert später der Reasoner.

### Rate-Limit (`llm/rate_limit.py`)

**Was tut es?**
Ein Token-Bucket pro Backend — begrenzt, wie viele Aufrufe pro Zeit durchgehen. Ist der Eimer leer, gibt es einen `RateLimited`-Fehler mit Wartezeit-Schätzung.

**Warum existiert es / wo sitzt es?**
Schutz vor Runaway-Kosten und Last (OWASP LLM10). Ein rate-limitiertes lokales Backend fällt bewusst **nicht** still auf die teure Cloud zurück. Die Uhr ist injizierbar — dadurch ohne echtes Warten testbar.

### Caching (`llm/cache.py`)

**Was tut es?**
Merkt sich Antworten unter einem gehashten Schlüssel aus Modell, Prompt, Quellen und Parametern; ein identischer Aufruf kommt byte-identisch aus dem Cache zurück.

**Warum existiert es / wo sitzt es?**
In Tests erzwingt das Determinismus; im Betrieb spart es Kosten/Latenz (zuschaltbar). Der Schlüssel ist ein Hash — kein Klartext, keine PII.

### Gateway-Metriken (`observability/metrics.py`, erweitert)

**Was tut es?**
Zählt je Gateway-Call Backend, Task, Latenz, Tokens, geschätzte Kosten, Fallbacks und Cache-Treffer — sichtbar unter demselben `GET /metrics`.

**Warum existiert es / wo sitzt es?**
Dieselbe Registry wie F4, nur erweitert. Labels bleiben niedrig-kardinal (Backend/Task), nie PII — so bläht die Metrik nicht auf und verrät nichts.

### Red-Team-Harness & Smoke (`tests/llm/security/redteam_harness.py`, `tests/llm/smoke/`)

**Was tut es?**
Das Harness fährt einen erweiterbaren Satz Injection-Payloads gegen die Spotlighting-/Grounding-Mechanik (steht grün). Der Smoke-Test macht einen **echten** Round-Trip gegen lokales Ollama und überspringt sauber, wenn keines läuft.

**Warum existiert es / wo sitzt es?**
Beweist, dass die Abstraktion real durchläuft, ohne CI an Ollama zu koppeln — und legt das Sicherheits-Gerüst bereit. Die scharfe Aktivierung mit echten Werker-Freitext-Payloads kommt mit dem ersten Freitext-Reasoner (Ereignisketten).

---

## F6 — Ereignisketten-Reasoner (`src/foreman/reasoners/event_chain/`)

Der erste LLM-Freitext-Reasoner und erste Konsument des `LLMGateway`. Saubere Schichtung: Sammeln → Grounden → Synthetisieren → Persistieren — jede Stufe für sich testbar. Die zentrale Frage hier ist nicht „erzählt es schön", sondern „hält das Grounding, wenn eine Werkernotiz versucht, den Reasoner zu kapern".

### Output-Schema (`event_chain/schema.py`)

**Was tut es?**
Nagelt die Output-Form zuerst fest: `EventChain` (zeitlich geordnete Ereignisse) und das validierte `ReasonerExplanation` (Erzähltext, referenzierte/geflaggte Quellen, Konfidenz/Hypothese, Grounding-Report). Plus Request- und API-Read-Schema.

**Warum existiert es / wo sitzt es?**
Der `model_validator` von `ReasonerExplanation` ist der **Output-Guard**: `referenced_source_ids ⊆ allowed_source_ids` und `extra=forbid`. Eine erfundene Quelle kann so nie als „belegt" durchrutschen — Schutz-Doc §5.1.

### Ketten-Konstruktion (`event_chain/chain.py`)

**Was tut es?**
`reconstruct_chain` sammelt um einen Anker-Alarm in einem Zeitfenster die relevanten Ereignisse (vorausgehende Alarme, Werkernotizen, Wartungen) — Auswahl über `machine_id` + Fenster, temporal geordnet.

**Warum existiert es / wo sitzt es?**
Reiner Kern ohne DB/Netz (Reihen werden injiziert) → isoliert testbar. Werkernotizen tragen hier schon `trusted=False` — die Invariante wandert über `ChainEvent.trusted` in die Quellen.

### NEXUS-Recall (`event_chain/recall.py`)

**Was tut es?**
Bildet aus dem Anker-Muster (Maschinenklasse + Alarm-Signatur, PII-frei) eine Recall-Query und ruft ähnliche Vergangenheits-Vorfälle über den `SubstrateClient` ab.

**Warum existiert es / wo sitzt es?**
Die „hatten wir das schon mal?"-Funktion — strikt best-effort: kein Substrat / Ausfall → leere Liste, die Kette wird ohne Recall-Anteil erzählt. Blockiert nie.

### Grounding-Quellen (`event_chain/grounding_sources.py`)

**Was tut es?**
Mappt Kette + Recall auf die `GroundingSource`-Liste fürs Gateway, jede mit eindeutiger `source_id`.

**Warum existiert es / wo sitzt es?**
**Die zentrale Sicherheits-Invariante:** `worker_notes` (und Recall) gehen IMMER als `trusted=False` rein (Spotlighting-Quelle, nie Instruktion); nur strukturierte Alarm-/Wartungsdaten sind `trusted=True`. Die Funktion hebt eine untrusted Quelle nie auf trusted an.

### Prompts (`event_chain/prompts.py`)

**Was tut es?**
System-/User-Prompt für die deutsche Erzählung: nur aus den Quellen, Hypothesen markiert, Zitate als `[source_id]`.

**Warum existiert es / wo sitzt es?**
Der untrusted Notiz-Freitext kommt nur gespotlightet über die Quellen — der User-Prompt enthält nur strukturelle Metadaten (Zeit/ID/Typ), nie inline den Freitext.

### Orchestrierung & Output-Guard (`event_chain/service.py`)

**Was tut es?**
Fährt die Pipeline (chain → recall → sources → `gateway.complete(task=synthesis)` → Output-Guard) und persistiert die Erklärung + spiegelt sie als `semantic_event`.

**Warum existiert es / wo sitzt es?**
`build_explanation` ist die scharfe Abwehr: zitierte Quellen gegen die Whitelist prüfen (erfundene → `flagged_unsupported`), unbelegte Zahlen aus dem Grounding-Report flaggen, Erzählung output-sanitisieren (HTML/Markdown/URL, LLM05). Geflaggt ⇒ Hypothese + Konfidenz `low`. Keine Aktorik.

### Persistenz (`migrations/versions/0003_reasoner_explanations.py`, `db/models.py`)

**Was tut es?**
`reasoner_explanations`-Tabelle (Migration 0003) + ORM-Model `ReasonerExplanationRecord`. Dual-Write als `semantic_event` (best-effort) macht das Reasoning-Ergebnis Teil des Gedächtnisses.

**Warum existiert es / wo sitzt es?**
Abfragbar fürs Dashboard/MCP. Gespiegelt wird eine strukturierte Zusammenfassung, **nicht** der rohe Erzähltext (defensiv gegen eingeschleusten Freitext im Substrat).

### Routen & Gateway-Dependency (`event_chain/router.py`, `api/deps.py`)

**Was tut es?**
`POST /reconstruct` (on-demand) + `GET /explanations(/{id})`. `api/deps.py` bekommt die erste `GatewayDep` (F6 = erster Konsument).

**Warum existiert es / wo sitzt es?**
On-demand, **kein** Auto-LLM pro Alarm — der alarm-getriebene Hook bleibt offen (Kostenkontrolle). POST ist auth-pflichtig. Die Dependency liefert das Gateway als Protokoll-Typ (kein LiteLLM in reasoner-fähigen Pfaden).

### Metriken (`observability/metrics.py`, erweitert)

**Was tut es?**
`foreman_event_chain_explanations_total` (sauber/geflaggt) + `foreman_event_chain_recall_total` (Treffer/kein Treffer) unter `GET /metrics`.

**Warum existiert es / wo sitzt es?**
Die geflaggt-Quote ist die Injection-Containment-Sicht; niedrig-kardinal, keine PII.

### Red-Team scharf (`tests/reasoners/event_chain/security/test_injection.py`)

**Was tut es?**
Fährt die echten `INJECTION_PAYLOADS` (aus dem F-LLM-Harness, via `build_worker_note`) als `worker_notes`-Freitext gegen die **reale** Pipeline.

**Warum existiert es / wo sitzt es?**
Die Kern-Akzeptanz von F6: Spotlighting hält, der Output-Guard flaggt erfundene Quellen/Zahlen, die Erzählung wird sanitisiert, das Schema validiert, der Reasoner bleibt inert (keine Aktorik). Plus False-Positive-Kontrolle.

---

## F-SEM — Semantische Notiz-Suche (`src/foreman/embeddings/`, `src/foreman/notes/`)

Eine Querfunktion, kein neuer Reasoner. Sie füllt das von F6 leer gelassene `worker_notes.embedding` und beantwortet die „hatten wir das schon mal?"-Frage auf der Notiz-Ebene. Tragendes Prinzip wie beim Gateway (§13): eine eigene, dünne Abstraktion, hinter der die konkrete Library verschwindet — Embeddings sind ein **anderer Pfad** als Completion und bekommen eine **parallele**, gleich geformte Schicht, kein Anbau am `LLMGateway`.

### Embedding-Fehler & Config (`embeddings/errors.py`, `embeddings/config.py`)

**Was tut es?**
Typisierte, deutschsprachige Fehlerhierarchie (`EmbeddingError` → `ProviderUnavailable`/`DimensionMismatch`/`EmbeddingTimeout`) und die `EmbeddingSettings` (env-Prefix `FOREMAN_EMBED_`: Priority, `bge-m3`, Dimension 1024, L2-Normalisierung, Ollama-URL, Timeout, Batch-Größe).

**Warum existiert es / wo sitzt es?**
Vorbild ist der Gateway-Vertrag (§13.5): ein Aufrufer fängt alles mit `except EmbeddingError`, ohne je eine Backend-/Library-Ausnahme zu sehen.

### Provider & Orchestrierung (`embeddings/provider.py`)

**Was tut es?**
Das `EmbeddingProvider`-Protokoll (`async embed(texts) -> list[Vector]`) + `LocalEmbeddingProvider`: Batch-Routing/Fallback → Dimension erzwingen (1024) → L2-Normalisierung → Metriken + Log. Plus `embed_best_effort` (Schreibpfad-Helfer).

**Warum existiert es / wo sitzt es?**
Die EINZIGE Fläche, die Ingestion/Suche/Reasoner berühren — kein Backend-/Library-Typ in der Signatur (harte Architektur-Grenze, analog §13.1).

### Backends & Fallback (`embeddings/backends.py`)

**Was tut es?**
Ollama-Backend (`POST /api/embed`, httpx) + sentence-transformers-Alternative (lazy) hinter dem `EmbeddingBackend`-Protokoll; `resolve_chain`/`run_with_fallback` für die vier Priority-Modi.

**Warum existiert es / wo sitzt es?**
DIE einzige Datei, die die konkreten Embedding-Libraries berührt; jede Fremd-/HTTP-Ausnahme wird in einen typisierten Embedding-Fehler übersetzt — nichts Library-Spezifisches verlässt das Modul.

### Backfill-Runner (`embeddings/backfill.py`)

**Was tut es?**
`backfill_embeddings` zieht `embedding IS NULL` batchweise nach; CLI `python -m foreman.embeddings.backfill`.

**Warum existiert es / wo sitzt es?**
Der „Nachhol"-Pfad zum best-effort-Insert (idempotent, Vordergrund-Prozess, §3). Anders als der Insert ist er **ehrlich** — ein Provider-Fehler propagiert.

### HNSW-Index & Suche (`migrations/versions/0004_worker_notes_hnsw.py`, `notes/search.py`)

**Was tut es?**
Migration 0004 legt den HNSW-Index (`vector_cosine_ops`, `m=16`, `ef_construction=200`) an. `search_similar_notes` ist die **reine** DB-Query mit fertigem Vektor; `embed_and_search` die Komposition (embedden, dann suchen).

**Warum existiert es / wo sitzt es?**
Die reine Query ist ohne Provider/Netz testbar; die Komposition trennt das „relevant" vom „zeitnah". Cosine erwartet L2-normierte Vektoren (Provider garantiert das).

### Such-Route (`notes/router.py`, `api/deps.py`)

**Was tut es?**
Read-only `GET /api/v1/worker_notes/search` (`q`/`machine_id`/`k`), auth-pflichtig. `api/deps.py` bekommt die `EmbeddingProviderDep`.

**Warum existiert es / wo sitzt es?**
**Vor** dem worker_notes-CRUD gemountet (sonst fängt `/{note_id}` den `/search`-Pfad). Ehrlich: 503 bei Backend-Ausfall (kein stilles Leer-Ergebnis) — anders als die best-effort F6-Anbindung.

### Embedding beim Insert (`ingestion/service.py`, `api/routers/worker_notes.py`)

**Was tut es?**
Der Ingestion-Service bettet die Notizen als EIN Batch vor jedem Commit ein; der CRUD-POST einzeln. Beide best-effort über `embed_best_effort` (eingebettet wird der NER-maskierte Text).

**Warum existiert es / wo sitzt es?**
Provider-Ausfall → `embedding=NULL`, die Notiz wird **trotzdem** geschrieben (analog Substrat-Dual-Write §12.4); der Backfill holt es nach. Der Schreibpfad blockiert nie auf der Embedding-Verfügbarkeit.

### F6-Anbindung (`reasoners/event_chain/chain.py`, `reasoners/event_chain/service.py`)

**Was tut es?**
`reconstruct_chain` bekommt `semantic_notes` (fenster-exempt, dedupliziert über `note.id`). Der Service baut die PII-freie Anker-Signatur (`build_anchor_signature`) und zieht semantisch ähnliche Notizen über `embed_and_search` — strikt best-effort.

**Warum existiert es / wo sitzt es?**
Die semantische Auswahl **ergänzt** die zeitnahe additiv; Provider/Suche-Ausfall → Zeitfenster-Fallback (blockiert nie, analog NEXUS-Recall §14.1). **Sicherheits-Invariante unverändert:** eine Notiz bleibt `trusted=False`, egal ob zeitlich oder semantisch ausgewählt — die F6-Tests inkl. Red-Team bleiben grün.

### Embedding-Metriken & Smoke (`observability/metrics.py`, `tests/embeddings/smoke/`)

**Was tut es?**
`foreman_embed_requests_total` (`backend`/`result`) + `foreman_embed_latency_seconds` + `foreman_embed_texts_total` über `observe_embedding`. `@smoke`-Test gegen echtes Ollama `bge-m3`, skippt sauber ohne lokales Ollama.

**Warum existiert es / wo sitzt es?**
Beobachtbarkeit je Backend (niedrig-kardinal, keine PII/keine Vektoren); der Smoke beweist den realen Round-Trip, ohne das Pflicht-Gate an Ollama zu koppeln.

---

## F-PRED — Ausfallvorhersage-Reasoner (`src/foreman/reasoners/failure/`)

> **Ehrlich deklarierter Methoden-Demonstrator.** Auf Simulationsdaten trainiert — die Pipeline ist verifizierbar, ohne reale Run-to-failure-Daten aber nicht validierbar. Der Vorbehalt ist strukturell erzwungen (`validation_status=simulation_only` Pflichtfeld, `data_regime=simulation` Metrik-Label). Ausführliche Begründung: `docs/models/failure_prediction_model_card.md`.

### Output-Schema (`failure/schema.py`)

**Was tut es?**
`FailurePrediction` (Pydantic, `extra=forbid`): Wahrscheinlichkeit, Horizont, Entscheidung, SHAP-`top_factors` — und **`validation_status` als Pflichtfeld ohne Default** (einziger Wert `simulation_only`), `data_regime`, `model_version`. Plus `PredictRequest` und `FailurePredictionRead` (API-Out).

**Warum existiert es / wo sitzt es?**
Die Ehrlichkeit zuerst festgenagelt: eine Vorhersage kann nicht ohne ihren Vorbehalt existieren. Konsistenz-Invarianten (decision↔Schwellwert, tz-aware) per `model_validator`.

### Feature-Extraktion (`failure/features.py`)

**Was tut es?**
Reine, netzfreie Funktion: aus einem Vorlauf-Fenster VOR dem Bezugszeitpunkt ein Feature-Vektor — `readings_1m`-Aggregate je Datenpunkt (Mittel/Std/Min/Max/Range/RMS/Trend/RoC/Last), Drift-Output als Feature (Anzahl/Stärke/Zeit-seit), Wartung (Zeit seit letzter Wartung), Alarm-Historie. `to_vector` füllt fehlende Features mit NaN.

**Warum existiert es / wo sitzt es?**
Der reine Kern (DB injiziert, ohne Netz testbar). **Strikt kein Zeit-Leakage** (nur Daten `< reference_time`); **PII-frei** (Zahlen über `data_points.name`, der Training und Inferenz konsistent verbindet).

### Trainingsdatensatz (`failure/dataset.py`)

**Was tut es?**
Baut je Lauf (Szenario/Seed) die Mess-Reihen in-memory über `signals.py`, leitet Drift-Events über `detect_drift_in_stream` ab, tastet Bezugszeitpunkte ab und labelt aus `ground_truth.failure` + Horizont. `split_by_seed` trennt **disjunkte Läufe**; `class_balance`/`matrix` für das Training.

**Warum existiert es / wo sitzt es?**
Offline-Trainingspfad, rein/netzfrei. Der lauf-disjunkte Split ist die Anti-Leakage-Garantie (kein zeilenweises Mischen von Fenstern desselben Laufs).

### Offline-Training (`failure/train.py`)

**Was tut es?**
CLI (`python -m foreman.reasoners.failure.train`): LightGBM (binär, `scale_pos_weight`, kein SMOTE), reproduzierbar (Seed), Eval mit PR-AUC/ROC-AUC/Brier auf dem lauf-disjunkten Split, kostensensitiver Schwellwert auf der PR-Kurve. Speichert Artefakt + Metadaten; druckt das Ehrlichkeits-Banner (`train_summary`).

**Warum existiert es / wo sitzt es?**
FOREMAN trainiert nicht zur Laufzeit (§10.4) — ein reproduzierbarer Vordergrund-Schritt. Die Eval-Metriken sind **Funktionsnachweis, kein Realitätsnachweis** (so im Log benannt).

### Inferenz (`failure/model.py`)

**Was tut es?**
Lädt das Artefakt-Verzeichnis (`model.txt` + `metadata.json`); `predict` liefert die Wahrscheinlichkeit (autoritativ vom Modell) + SHAP-Top-Faktoren via `TreeExplainer`. Fehlende Features (NaN) tauchen nicht als Faktor auf. Gebündeltes Demonstrator-Artefakt unter `artifacts/failure_lgbm`.

**Warum existiert es / wo sitzt es?**
Die Inferenz-Schale; `validation_status`/`data_regime`/`model_version` stammen aus den Metadaten und werden durchgereicht.

### Persistenz & Orchestrierung (`migrations/versions/0005_failure_predictions.py`, `db/models.py`, `failure/service.py`)

**Was tut es?**
Migration `0005` legt `failure_predictions` an (inkl. Vorbehalt-Spalten + Lese-Index). `FailureService` lädt die DB-Daten (readings_1m, Drift-Events aus `drift_detected`-`semantic_events`, Wartung, Nicht-Drift-Alarme), baut die `FailurePrediction` und persistiert sie.

**Warum existiert es / wo sitzt es?**
Die dünne IO-Schale um die reinen Kerne. **Kein Auto-Predict, keine Aktorik.** Der Vorbehalt überlebt die Speicherung.

### Routen & Modell-Dependency (`failure/router.py`, `api/deps.py`)

**Was tut es?**
On-demand `POST /api/v1/reasoners/failure/predict` (201) + `GET …/predictions(+{id})`. `FailureModelDep` lädt das Artefakt einmalig (lru_cache; Override `FOREMAN_FAILURE_MODEL_PATH`).

**Warum existiert es / wo sitzt es?**
Auth-pflichtig, on-demand (Konsistenz mit F6); jede Antwort führt den Sim-Vorbehalt mit.

### Metriken & Szenario-Erweiterung (`observability/metrics.py`, `adapters/simulation/scenario.py`)

**Was tut es?**
`foreman_failure_predictions_total` (`data_regime`/`decision`) + `foreman_failure_probability` (`data_regime`) über `observe_failure_prediction`. Szenario-Format additiv um `ground_truth.failure` (strikt) erweitert; `bearing_drift`/`tool_wear`/`lubrication_correlation` mit Ausfall versehen.

**Warum existiert es / wo sitzt es?**
`data_regime=simulation` ist Pflicht-Label — der Vorbehalt ist im Monitoring sichtbar. Die Szenario-Erweiterung ist additiv (F4-Tests grün).

### Tests & Kern-Akzeptanz (`tests/reasoners/failure/`)

**Was tut es?**
Reine Stufen ohne Netz (Schema/Features/Dataset/Model/Train) + E2E gegen echte DB (Service/Router). **Kern-Akzeptanz:** eine `FailurePrediction` ohne `validation_status` ist nicht konstruierbar; die E2E-Pipeline trägt `simulation_only` IMMER. Kein-Leakage und lauf-disjunkter Split sind getestet.

**Warum existiert es / wo sitzt es?**
Verifikation der Pipeline (nicht Validierung der Vorhersage — diese Grenze ist der Kern der Model Card).

---

## F-REC — LLM-Werker-Empfehlung (`src/foreman/reasoners/failure/`, Erklär-Layer)

> **Die Ehrlichkeit in die Sprache getragen.** Der Erklär-Layer über F-PRED und **zweiter Konsument des `LLMGateway`** nach F6. Aus einer bestehenden `FailurePrediction` macht das LLM eine deutsche, handlungsleitende Werker-Empfehlung. Zwei Invarianten sind strukturell erzwungen: **(I)** Zahlen autoritativ vom Modell (numerischer Post-Check *rejectet* unbelegte Zahlen — anders als F6, das *flaggt*), **(II)** deterministischer Sim-Vorbehalt (`validation_caveat`, nie LLM-generiert).

### Output-Schema (`failure/schema.py`, erweitert)

**Was tut es?**
`WorkerRecommendation` (Pydantic, `extra=forbid`, frozen): `recommendation_text` (geguardeter LLM-Output), `validation_caveat` (deterministisch), `validation_status`/`data_regime`/`model_version` (mitgeführt), `referenced_source_ids` ⊆ `allowed_source_ids`, und die aus der Vorhersage geerbten autoritativen Zahlen (`probability`/`horizon_h`/`decision`). Plus `validation_caveat_for(...)` (das deterministische Vorbehalts-Mapping) und `WorkerRecommendationRead` (API-Out).

**Warum existiert es / wo sitzt es?**
Die Ehrlichkeit zuerst festgenagelt: ein `model_validator` erzwingt `validation_caveat == validation_caveat_for(validation_status)` (Invariante II — der Vorbehalt ist nicht durch LLM-Text ersetzbar) **und** `referenced ⊆ allowed` (Output-Guard).

### NEXUS-Recall ähnlicher Vorlauf-Muster (`failure/recall.py`)

**Was tut es?**
`build_runup_query` bildet aus Maschinenklasse + Top-Faktor-Signatur + Entscheidung eine **PII-freie** Query; `recall_similar_runups` ruft über den `SubstrateClient` ähnliche frühere Vorläufe ab. Die defensive Mapping-Mechanik (`RecallItem`/`map_recall_response`) wird aus dem F6-Recall wiederverwendet.

**Warum existiert es / wo sitzt es?**
**Strikt best-effort:** kein Substrat / Ausfall → leere Liste (die Empfehlung wird ohne historischen Kontext erzeugt, blockiert nie). Recall-Inhalte sind externer Freitext → in den Grounding-Quellen untrusted.

### Grounding-Quellen (`failure/grounding.py`)

**Was tut es?**
`build_recommendation_sources`: die Vorhersage (`pred:<id>`) + je SHAP-Faktor (`factor:<name>`) als `trusted=True` (ihr Content trägt die autoritativen Zahlen — inkl. `machine_id`, damit sie belegt ist); je Recall-Treffer (`recall:<n>`) als `trusted=False`.

**Warum existiert es / wo sitzt es?**
Die Sicherheits-Invariante: nur was im trusted-Content steht, ist eine belegte Zahl (Beleg-Basis für den numerischen Post-Check). Recall-Freitext belegt nie eine Zahl.

### Prompts (`failure/prompts.py`)

**Was tut es?**
`RECOMMENDATION_SYSTEM_PROMPT` (Erklär-Layer, kein Akteur): nur aus den Quellen, **keine eigenen Zahlen einführen / nichts umrechnen**, den Sim-Charakter benennen, GENAU EINE Handlungsempfehlung mit Begründung über die Faktoren, keine Aktorik. `build_recommendation_user_prompt` liefert nur das strukturelle Faktor-Gerüst (Inhalt kommt gespotlightet über die Quellen).

**Warum existiert es / wo sitzt es?**
Reine, testbare Funktionen. Der untrusted Recall-Freitext geht nur über die (gespotlighteten) Quellen ins Gateway, nie inline.

### Orchestrierung & Guards (`failure/recommendation.py`)

**Was tut es?**
`RecommendationService.recommend`: lädt die `FailurePrediction` (404 wenn fehlt) → Recall → Grounding-Quellen → `gateway.complete(task=explanation)` → **(I) numerischer Post-Check** (`GroundingReport.unbacked` nicht leer → `NumericGroundingError`, harter Reject) → **(II) Negativ-Guard** (`detect_overclaim` → `RecommendationOverclaimError`) → `build_recommendation` (Output-Guard: Zitate gegen Whitelist, Sanitisierung LLM05, deterministischer Vorbehalt) → Persistenz + Dual-Write.

**Warum existiert es / wo sitzt es?**
Die zwei Invarianten als scharfe Gates: keine Empfehlung mit erfundener Zahl oder umgedeutetem Vorbehalt wird je persistiert. **Kein Auto-LLM, keine Aktorik.** Reasoner importiert nur `foreman.llm`.

### Persistenz & Dual-Write (`migrations/versions/0007_failure_recommendations.py`, `db/models.py`)

**Was tut es?**
Migration `0007` legt `failure_recommendations` an (FK auf `failure_predictions`, Caveat-/Vorbehalt-/Zahl-Spalten, CHECK-Constraints, Indizes). `_persist` schreibt den `FailureRecommendationRecord`; `_mirror` spiegelt eine PII-freie Zusammenfassung als `semantic_event` (`event_type=failure_recommendation`, **`data_regime=simulation`** im Payload).

**Warum existiert es / wo sitzt es?**
Defense-in-Depth: der Sim-Vorbehalt + die Entscheidung sind auch an der DB-Grenze erzwungen. Das Gedächtnis legt die Sim-Empfehlung nie als reale Prognose ab.

### Routen (`failure/router.py`, erweitert)

**Was tut es?**
On-demand `POST /api/v1/reasoners/failure/predictions/{prediction_id}/recommendation` (201) + `GET …/recommendation` (jüngste). 404 bei fehlender Vorhersage, 422 wenn der Grounding-/Vorbehalts-Guard die Empfehlung verwirft. Pfad unter dem `predictions/{id}`-Präfix (konsistent mit F-PRED + F6).

**Warum existiert es / wo sitzt es?**
Auth-pflichtig, on-demand (Kostenkontrolle, Konsistenz mit F6); jede Antwort führt den deterministischen Vorbehalt mit.

### Metriken & Red-Team (`observability/metrics.py`, `tests/reasoners/failure/security/test_recommendation_injection.py`)

**Was tut es?**
`foreman_failure_recommendation_total` (`data_regime`/`result`) + `foreman_failure_recommendation_recall_total` (`result`). Red-Team scharf über den **Recall-Pfad**: vergifteter Substrat-Inhalt kapert die Empfehlung nicht (Spotlighting hält, Output-Guard greift, numerischer Reject bei fabrizierter Zahl, Vorbehalt nicht umdeutbar, Inertheit).

**Warum existiert es / wo sitzt es?**
`data_regime=simulation` Pflicht-Label. Der Recall-Pfad ist die Angriffsfläche von F-REC (leichter als F6 — keine Werkernotizen — aber scharf geprüft).

---

## F7 — MCP-Schnittstelle (`src/foreman/mcp/`, offener Knoten)

> **Plattform statt App.** FOREMAN reicht die aggregierten Erkenntnisse der Reasoner als saubere, maschinenlesbare Tools an Drittsysteme (Simulation, ERP, Energiemanagement) — über das Model-Context-Protocol, **read-only**, remote über Streamable HTTP. Diese Schicht erfindet keine Logik; sie exponiert das schon Gebaute ehrlich gekennzeichnet, PII-geschützt und IP-wort-diszipliniert nach außen. Drei Invarianten tragen sie: **(I)** read-only, keine Aktorik, kein Reasoner-/LLM-Trigger über MCP; **(II)** AI-Act-Transparenz an jedem KI-Output (Art. 50(2)); **(III)** kein internes Vokabular in extern sichtbaren Strings.

### Transparenz-Wrapper (`mcp/transparency.py`)

**Was tut es?**
`AiTransparency` (Pydantic, frozen) ist der gemeinsame Umschlag, der in JEDES Tool-Ausgabeschema eingebettet wird: `ai_generated`, `generated_by` (= `foreman-ai`), `requires_human_review`, `model_version` und — bei Vorhersage/Empfehlung — `validation_status`/`data_regime`/`validation_caveat`. Builder `ai_transparency(...)` / `non_ai_transparency()`.

**Warum existiert es / wo sitzt es?**
Die Ehrlichkeit ist **strukturell** erzwungen: ein `model_validator` lässt einen unehrlichen Umschlag nicht zu — KI-Output MUSS den Erzeuger-Marker + die Review-Pflicht tragen, Nicht-KI-Daten dürfen KEIN KI-Metadatum führen. Die Flags sind ehrlich pro Output-Typ, nicht pauschal.

### Ausgabeschemata (`mcp/schemas.py`)

**Was tut es?**
Pydantic-Ausgabeschemata pro Tool (`MachineOut`, `AlarmOut`, `FailurePredictionOut`, `WorkerRecommendationOut`, `EventChainOut`, `NoteHitOut`, `ReadingsOut`, `DriftStatusOut`, …) — der **externe Vertrag**, bewusst entkoppelt von den internen Read-DTOs. Der Transparenz-Wrapper als gemeinsames Feld auf jedem Leaf-Output.

**Warum existiert es / wo sitzt es?**
PII-frei: nur HMAC-Token (`acknowledged_by`/`author`) und NER-maskierter Text raus, kein Embedding-Vektor, keine `users`-Felder. SHAP heißt nach außen neutral `contribution` (Invariante III).

### Read-Schicht (`mcp/reads.py`)

**Was tut es?**
Dedizierte Read-only-Datenzugriffsfunktionen (injizierte Session), die die Tools aufrufen — der saubere Service-Layer der Schnittstelle. Spiegelt die bereits existierenden Read-Pfade als wiederverwendbare Funktionen; aggregierte Trends über die Minuten-Aggregat-Sicht, semantische Notiz-Suche (Query einbetten + suchen, kein LLM).

**Warum existiert es / wo sitzt es?**
Architektur-Entscheidung (Review-geklärt): die Read-Logik lag bisher inline in den HTTP-Routern, ohne wiederverwendbare Service-Methode. Statt 6 Reasoner-Router zu refactoren bekommt MCP eine eigene, testbare Read-Schicht — chirurgisch, ausschließlich SELECT (Invariante I).

### Tools (`mcp/tools.py`)

**Was tut es?**
Elf read-only Tools (`list_machines`, `get_machine`, `get_drift_status`, `get_alarms`, `list_failure_predictions`, `get_failure_prediction`, `get_worker_recommendation`, `list_event_chains`, `get_event_chain`, `search_notes`, `get_readings`). Jedes öffnet eine eigene Read-only-Session (kein Commit), mappt den ORM-Datensatz auf das Ausgabeschema, hüllt KI-Output in die Transparenz-Flags und misst Latenz/Ergebnis als Metrik.

**Warum existiert es / wo sitzt es?**
Maschinen-`status` (gesund/Drift aktiv/offene Warnung) wird aus offenen Alarmen komponiert; `get_event_chain` filtert auf den Ereignisketten-Reasoner; Vorhersagen tragen den abgeleiteten, Empfehlungen den gespeicherten Vorbehalt. Kein Tool ruft je `predict`/`recommend`/`reconstruct` (das wären Compute+Write+LLM).

### Auth (`mcp/auth.py`)

**Was tut es?**
`McpSettings` (eigener `FOREMAN_MCP_`-Token als `SecretStr`, getrennt vom Plattform-JWT), `verify_mcp_token` (zeitkonstant, Fail-Closed), `McpAuthMiddleware` (reine ASGI: alles außer `/health`/`/metrics` hinter dem Token, 401-Reject) + ein Token-Bucket gegen Abruf-Last (429).

**Warum existiert es / wo sitzt es?**
Read-only-Zugriff für Drittsysteme — authentifiziert, getrennter Blast-Radius. Produktions-Fail-Fast: kein remote erreichbarer Server ohne sicheren Token (Repo ist öffentlich).

### Server & Metriken (`mcp/server.py`, `observability/metrics.py`)

**Was tut es?**
`build_mcp_server` registriert die Tools (alle mit `readOnlyHint=True`, IP-wort-disziplinierte Beschreibungen); `build_mcp_app` baut die eigenständige ASGI-App (Auth-Middleware + MCP-Transport + eigene `/health`/`/metrics`). `foreman_mcp_requests_total` (`tool`/`result`) + `foreman_mcp_latency_seconds` (`tool`).

**Warum existiert es / wo sitzt es?**
Eigenständig — berührt die Plattform-FastAPI-App nicht (eigener Token, eigener Port). Verifiziert durch echten SDK-Handshake, strukturellen Read-only-/No-Actuation-Beweis und den Hidden-Term-Scan über alle Tool-Strings (`tests/mcp/`).

---

## F5 — Dashboard-Backend & Live-Push

### Geteilter Read-Core (`reads/queries.py`, `reads/status.py`, `reads/overview.py`, `reads/trend.py`)

**Was tut es?**
Eine transport-neutrale Read-only-Schicht: die SELECT-Funktionen, die Status-Komposition (gesund / Drift aktiv / offene Warnung), das Flotten-Overview (Status + Alarme nach Severity + Rollup) und der Sensortrend (`readings_1m` + statisches Normalband). MCP, die HTTP-Routen und der Live-Push lesen alle hierüber.

**Warum existiert es / wo sitzt es?**
Eine Wahrheit statt mehrerer Kopien: die Read-Logik lag bisher teils in der MCP-Schicht. Sie ist jetzt zentral und ohne Transport (kein FastAPI, kein WebSocket) testbar; MCP ruft sie auf.

### NOTIFY-Producer (`realtime/notify.py`, `realtime/channels.py`)

**Was tut es?**
Setzt genau ein `pg_notify` pro Commit/Batch auf den Kanal `foreman_dashboard` — ein dünner Payload aus reinen IDs (kein Inhalt), bei Overflow ein „breites" Refresh-Signal statt abgeschnittener IDs. Verdrahtet im Ingest-Service (ein Signal je Tick-Commit) und in der Readings-Route.

**Warum existiert es / wo sitzt es?**
Der Ingest läuft als eigener Prozess, nicht in der API — Postgres-NOTIFY ist die entkoppelte Brücke (der Stack hat bewusst kein Redis/keine Queue). Transaktional: das Signal kommt erst beim Commit, nie für nicht-geschriebene Daten.

### Hub & Listener pro Worker (`realtime/hub.py`, `realtime/listener.py`, `realtime/wiring.py`)

**Was tut es?**
Jeder Worker hält eine eigene LISTEN-Verbindung und einen In-Process-Hub. Eingehende Signale werden pro Thema gebündelt (debounce), danach lädt der Endpoint frisch nach. Bricht die Verbindung ab, verbindet der Listener neu und stößt ein breites Refresh an (Snapshot-Reload).

**Warum existiert es / wo sitzt es?**
Postgres broadcastet NOTIFY an alle Worker; jeder bedient seine eigenen Clients — kein globaler Singleton. Debounce zuerst, dann laden: ein Schwall Readings erzeugt einen Lade-Vorgang, nicht hundert.

### WebSocket-Endpoint (`realtime/ws.py`)

**Was tut es?**
Ein gemultiplexter Kanal (`/api/v1/ws`): authentifiziert per Query-Token, nimmt subscribe/unsubscribe entgegen, schickt bei jedem erlaubten Abo sofort einen Snapshot und danach Live-Deltas — für Flotten-Overview, Maschinen-Status und Sensortrend.

**Warum existiert es / wo sitzt es?**
Eine Verbindung für viele Sichten statt ein Socket pro Kachel. Die Auth-Middleware greift bei WebSockets nicht, daher prüft der Endpoint das Token selbst und nutzt pro Lade-Operation eine kurze Read-only-Session.

### Abo-Autorisierung (`realtime/authz.py`)

**Was tut es?**
Entscheidet pro Abo (und pro HTTP-Route), ob die Rolle das Thema sehen darf: Werker nur seine Maschinen, Schichtleiter seine Linien, Manager/Techniker breit; das Cockpit nur Manager/Schichtleiter. Alles nicht ausdrücklich Erlaubte wird abgelehnt.

**Warum existiert es / wo sitzt es?**
Authentifiziert allein genügt nicht — ohne Scope-Prüfung könnte jeder eingeloggte Client jedes Maschinen-Thema mitlesen. Dieselbe Prüfung trägt WebSocket und HTTP, damit die Grenze nicht erst im Frontend entsteht.

### HTTP-Read-Routen (`api/routers/dashboard.py`)

**Was tut es?**
`GET /api/v1/overview` (Flotten-Lagebild) und `GET /api/v1/machines/{id}/trend` (Sensortrend + Normalband) — das Erstbild-/Pull-Gegenstück zum Live-Push, über denselben Read-Core und dieselbe Autorisierung.

**Warum existiert es / wo sitzt es?**
Das Frontend braucht ein Erstbild beim Laden (und einen Pull-Pfad, wenn kein Stream nötig ist); die Live-Sichten kommen danach über den WebSocket.

### Aktueller Nutzer (`api/routers/me.py`)

**Was tut es?**
`GET /api/v1/me` gibt Identität, Rolle und Per-User-Scope (`assigned_line_ids`/`assigned_machine_ids`) des eingeloggten Nutzers zurück — ohne Passwort-Hash. Auth-pflichtig; ohne gültiges Token 401.

**Warum existiert es / wo sitzt es?**
Das Frontend muss seine Navigation und Sichten nach der Rollenmatrix (3.1) filtern. Dafür braucht es Rolle und Scope des angemeldeten Nutzers — das Login gibt nur ein Token (Claim `sub`). `/me` liefert genau diese Information, damit das Frontend die Server-Autorisierung *spiegelt* (nicht ersetzt): die tatsächliche Grenze bleibt `can_subscribe`/die Read-Routen (§20.4). Read-only, keine Aktorik.

### WS-Ticket (`api/routers/ws_ticket.py`, `core/security.py`)

**Was tut es?**
`GET /api/v1/ws-ticket` gibt dem angemeldeten Nutzer ein kurzlebiges (60 s), WS-scoped Ticket (`aud="ws"`). Der WebSocket (`/api/v1/ws`) akzeptiert dieses Ticket *oder* ein Session-JWT; ein Ticket ist auf HTTP-Routen nicht gültig.

**Warum existiert es / wo sitzt es?**
Der WebSocket erzwingt ein Token im `?token=`-Query, das clientseitiges JS bauen muss. Würde dort das volle Session-JWT (httpOnly-Cookie) herausgegeben, wäre der Cookie-Schutz für dieses Token aufgehoben. Das kurzlebige, scope-begrenzte Ticket hält den Schaden bei einem Query-/JS-Leak klein: es läuft schnell ab und gilt nur am WebSocket. `decode_ws_token` prüft die Audience; `decode_access_token` (HTTP) lehnt audience-tragende Tokens ab.

---

## F5-FE — Frontend-Fundament (`frontend/`)

### Token-Quelle (`frontend/tokens/`, `frontend/scripts/build-tokens.ts`)

**Was tut es?**
Eine einzige Quelle in drei Ebenen (primitive → semantisch → Theme dark/hc-light) erzeugt per Generator die `app/styles/tokens.generated.css` — daraus speisen sich sowohl die Tailwind-Utilities als auch die Runtime-CSS-Variablen. Ein Test rechnet die WCAG-Kontraste beider Themes nach (Status ≥7:1, Körper ≥4.5:1, Grafik ≥3:1).

**Warum existiert es / wo sitzt es?**
ISA-101 verlangt eine ruhige, entsättigte Fläche, auf der Farbe nur Bedeutung trägt. Eine zentrale Token-Quelle hält das konsistent: ein Theme-Wechsel ändert eine Ebene, nicht hunderte Komponenten. Das UI nutzt nur semantische Namen.

### Echtzeit-/State-Schicht (`frontend/lib/realtime/`, `frontend/lib/state/`)

**Was tut es?**
Ein gemultiplexter WebSocket-Client spricht den realen `/api/v1/ws`-Vertrag (Themen-Abos, Reconnect mit erneutem Abonnieren = Snapshot-Reload, Close 4401). Ein Stream-Store puffert und drosselt eingehende Daten; eine abgeleitete Ebene leitet daraus die fünf Pflichtzustände ab (live/gecacht/lädt/leer/Fehler). Komponenten lesen nur die abgeleitete Ebene.

**Warum existiert es / wo sitzt es?**
Die strikte Entkopplung von Transport und Visualisierung ist die tragende Architekturentscheidung (Designstudie §5.1): eine Sicht ist gegen WebSocket, Cache oder Testdaten austauschbar — bewiesen durch Tests gegen einen Fake-Transport. So kippt Reacts Freiheit nicht in Chaos.

### BFF & Auth (`frontend/lib/auth/`, `frontend/app/api/`)

**Was tut es?**
Ein Route-Handler-Proxy reicht `/api/v1`-Aufrufe ans Backend weiter und injiziert das JWT aus einem httpOnly-Cookie als Bearer; Login/Logout/Session und ein WS-Ticket laufen über eigene Route-Handler. Rolle und Scope kommen aus `GET /api/v1/me`.

**Warum existiert es / wo sitzt es?**
Das Token bleibt vor Browser-JS geschützt und das Backend braucht keine CORS-Lockerung (chirurgisch, kein Backend-Change). Das Frontend spiegelt die Server-Autorisierung (Rollenmatrix 3.1), ersetzt sie nie — Guards leiten unerlaubte Direktaufrufe auf das rollenspezifische Landing.

### Atome, Shell & Durchstich (`frontend/components/`, `frontend/views/overview/`)

**Was tut es?**
Plattform-Atome (StatusIndicator mehrkanalig, ProvenanceStamp, KpiTile, Fünf-Zustände-Hülle) und die persistente Shell (globale Statusleiste live, Breadcrumb, Befehlsleiste ⌘K, Schnellerfassung, rollengefilterte Navigation). Der vertikale Durchstich zeigt die Flotten-Übersicht: Erstbild per HTTP-Snapshot, Live-Aktualisierung per WS-Thema.

**Warum existiert es / wo sitzt es?**
Der Durchstich beweist, dass Token → Atom → State-Schicht → WS/HTTP → Backend zusammenspielen und die fünf Zustände sichtbar funktionieren — das Fundament, auf dem jede künftige Sektion ruht, ohne es anzufassen.

### Sektion C — Alarme & Warnungen (`frontend/lib/alarms/`, `frontend/components/alarms/`, `frontend/app/(app)/alarms/`)

**Was tut es?**
Die erste voll ausgebaute Sektion zeigt offene Alarme **nach Dringlichkeit gestaffelt** (ISA-18.2: kritisch oben, nicht chronologisch-flach), virtualisiert (nur Sichtbares im DOM), mit Prioritäts-Zählern, Filter und Gruppierung (Priorität/Bereich/Maschine). Jede Zeile codiert die Severity dreikanalig (Farbe + Position + Label) und trägt einen FCSM-Indikator; ein langsamer 1-Hz-Puls markiert **nur** unquittiert-kritische Alarme (nicht die Severity). Neue Alarme kommen über ein WS-Aggregat-Signal herein, werden nachgeladen und an ihrer Sortier-Position mit kurzem Einblend-Puls eingefügt — ohne Listen-Sprung. Der Schichtleiter quittiert zweistufig (Pflicht-Begründung bei kritisch); Werker lesen nur, der Manager sieht ein reines Lagebild. Alarmlawinen einer gemeinsamen Quelle werden zu einem Bündel zusammengefasst.

**Warum existiert es / wo sitzt es?**
`lib/alarms/` ist die reine, transport-agnostische View-State-Logik (Sortierung, Gruppierung, Flood-Bündelung, Lebenszyklus, Virtualisierungs-Mathematik) — ohne UI testbar; `components/alarms/` ist die rein präsentationale Sicht darüber, `app/(app)/alarms/page.tsx` der server-seitige Einstieg mit Sektions-Guard. Die harte Haltung: Quittieren/Eskalieren/Zurückstellen sind **Alarm-Status-Aktionen**, nie eine Anlagen-Schaltung — eine Sicherheits-Invariante lässt vor dem Senden ausschließlich den `…/acknowledge`-Pfad zu. Die Sicht sitzt vollständig auf dem FE1-Fundament auf (Tokens, Echtzeit-Schicht, StatusIndicator, Fünf-Zustände-Hülle, GlobalStatusBar) und dupliziert nichts. Offene Backend-Lücken (generische Quittier-Route, Listen-Scope, Shelving-Persistenz, zeitgesteuerte Eskalation) sind als markierte Anschlusspunkte gebaut, nicht erfunden (GROUND_TRUTH §21.9).

### Sektion E — Ausfallvorhersage & Empfehlung (`frontend/lib/prediction/`, `frontend/components/prediction/`, `frontend/lib/ondemand/`, `frontend/components/ondemand/`, `frontend/app/(app)/insights/prediction/`)

**Was tut es?**
Die zweite voll ausgebaute Sektion beantwortet vier Fragen in einer einzigen Karte, in fester Reihenfolge: wie wahrscheinlich ist ein Ausfall (Konfidenz als grobe verbale Stufe + Band über dem Vorlauf-Horizont, **keine** Schein-Prozentzahl), warum (Einflussfaktoren in Werker-Sprache, Richtung per Pfeil+Wort und Gewicht per Balken+Wort — farbunabhängig, **ohne** Verfahrensnamen), was tun (eine Empfehlung, immer als **Vorschlag**), und — untrennbar im selben Rahmen — der **Vorbehalt** (note/caveat, festes Symbol): „beruht auf simulierten Verläufen, nicht feldvalidiert". Der Schichtleiter fordert eine frische Vorhersage an (benannter Verarbeitungszustand statt Spinner) und quittiert oder verwirft die Empfehlung mit Begründung; Werker lesen knapp, Techniker mit Faktor-Detail, der Manager sieht nur ein aggregiertes Risikobild — nie die Einzelempfehlung als Befehl.

**Warum existiert es / wo sitzt es?**
E trägt die schärfste der drei Haltungen: man kann die Wahrscheinlichkeit nie sehen, ohne im selben Blick den Vorbehalt zu sehen — Konfidenz und Vorbehalt teilen einen `<article>`-Rahmen, der Vorbehalt ist nie wegklappbar, sein Text kommt **deterministisch** vom Backend (`validation_caveat`), und ein **Negativ-Guard** rendert beim Fehlen des Vorbehalts den Fehler-Zustand statt einer nackten Zahl (`lib/prediction/view-model.ts`). `lib/prediction/` ist die reine, transport-agnostische Logik (Konfidenz, Faktor-Paraphrase, Vorbehalt-Guard, HITL-Entscheidung, Vier-Block-Komposition) — ohne UI testbar; `components/prediction/` die präsentationale Karte. E etabliert zugleich das **geteilte On-Demand-Muster** (`lib/ondemand/` + `components/ondemand/`: Trigger → benannter Zustand → Ergebnis mit Herkunft), das die späteren Sektionen D/F/G/H erben. Die Empfehlung ist nie mit einer Schaltung verknüpft (HITL); die Entscheidung ist client-seitig auditierbar, weil das Backend (noch) keine Entscheidungs-Route hat. Sitzt vollständig auf dem FE1-Fundament auf (Tokens, ProvenanceStamp, Fünf-Zustände, BFF) und dupliziert nichts (GROUND_TRUTH §21.10).

---

### Sektion B — Maschinen-Detail (`frontend/lib/machine/`, `frontend/components/machine/`, `frontend/app/(app)/machines/`)

Die zentrale Drill-down-Sicht und das Ziel vieler Querlinks. Leitfrage: "Wie geht es dieser Maschine — jetzt und im Verlauf — und weicht sie von ihrem eigenen Normalverhalten ab?" Erste [KERN]-Sektion. Voller Vertrag: GROUND_TRUTH §21.11.

**Was ist es / wo sitzt es?**
- Reine, transport-agnostische Logik in `lib/machine/`: `trend-series.ts` verschmilzt den historischen `/trend`-Pull (by NAME) mit dem Live-1-h-Fenster (WS-Thema `trend:{data_point_id}`, das bei jedem Reading das ganze Fenster neu pusht) auf dem `bucket`-Schlüssel — der Live-Rand atmet, ohne dass ältere Punkte oder die Achse springen; `deriveDriftSegments` leitet Über-/Unterschreitungen des Normalbands ab. Dazu `geometry.ts` (lineare SVG-Skalen + Pfade), `time-window.ts` (Schicht/Tag/Woche; Monat/9 Monate = [VISION], Backend deckelt bei 168 h), `history.ts` (Wartung + Notizen vereint, PII maskiert über `lib/ui/pii.ts` → `#hex6`), `roles.ts`, `url.ts`, sowie die Hooks `use-machine-trend` (Pull + Live → eine Reihe, fünf Zustände) und `use-machine-history` (blätterbarer Pull).
- `components/machine/TimeSeriesChart` ist ein maßgeschneidertes, token-getriebenes SVG (bewusst KEINE Charting-Lib — hält das <100-kB-Erstbild-Ziel, volle Kontrolle über die Kodierung): Normalband als entsättigte Fläche, Drift als Differenzfläche (`diff-over`/`diff-under` + Schraffur-Pattern), Eigenprofil graceful (`profile_band` null → kein erfundener Strich), mehrkanalig (Linie + Fläche + Schraffur + aria-Label), Drift als Akzent — nie Alarm-Rot. Dazu `MachineHeader` (Identität + FCSM groß live über `machine:{id}` + Schnellaktionen), `MachineSpecs`, `MachineHistory` (PII maskiert), `MachineAlarms` (bettet die C-`AlarmRow` ein, maschinengefiltert — kein dupliziertes Rendering), `MachineList`, `MachineCrossLinks`, `SensorPicker`/`TimeWindowPicker`, `MachineDetailView` (Orchestrator, Rollen-Split ohne bedingte Hooks).
- Routen: `app/(app)/machines/page.tsx` (Übersicht, scope-gefiltert) + `app/(app)/machines/[id]/page.tsx` (Detail, SSR-Stammdaten, `requireSection("B")`).

**Warum so?**
- Transport-Entkopplung (Studie §5.1): der Chart liest nur den abgeleiteten View-State und ist gegen live/historisch/Testdaten austauschbar. HITL hart: die Schnellaktionen (Notiz → J, Vorhersage → E, Ereigniskette → D) sind Navigation/Anforderung, nie Anlagen-Aktorik. PII (§8) wird immer maskiert gezeigt; Drift ist eine Beobachtung (Akzent), kein Alarm. Rollen-Varianten nach Matrix 3.1, Sichtbarkeit ≤ Server-Guard.

### Sektion H — Gedächtnis & Verknüpfung (`frontend/lib/memory/`, `frontend/components/memory/`, `frontend/app/(app)/memory/`)

FOREMANs Alleinstellung und die zweite [KERN]-Sektion: die Bedeutungssuche "hatten wir das schon mal — irgendwo, an irgendeiner Maschine, in irgendeiner Schicht?". Klassische Observability sammelt und visualisiert; sie kann nicht "ähnliche Vorfälle finden" — genau das ist der Beweis, dass FOREMAN ein Gedächtnis hat. Eigener, begehbarer Raum (`/memory`) und von überall über die Befehlsleiste (Cmd-K → H). Voller Vertrag: GROUND_TRUTH §21.12.

**Was ist es / wo sitzt es?**
- Reine, transport-agnostische Logik in `lib/memory/`: `view-model.ts` führt die F-SEM-Antwort (`list[WorkerNoteRead]`, nach Nähe sortiert, OHNE Score) in ein anzeigbares Ergebnis über und bewahrt die Backend-Reihenfolge als Rang (= Relevanz-Signal); `relevance.ts` leitet daraus eine grobe, ordinale Nähe-Stufe ab — niemals eine Prozentzahl; `cluster.ts` verdichtet Treffer derselben Maschine ("3 Hinweise an Maschine X"); `relations.ts` verknüpft Treffer NUR über real ableitbare Bezüge (gleiche Maschine, gleiche Schicht, zeitliche Nähe). Dazu `excerpt.ts`, `time.ts` (relative Hallensprache, injizierbares "jetzt"), `roles.ts`, `url.ts` und der On-Demand-Hook `use-memory-search.ts` (geteilter Reducer aus `lib/ondemand/` + AbortController + sessionStorage-Cache für Offline).
- `components/memory/`: `MemorySearchBar` (die einladende, natürlichsprachliche Suchzeile — das Tor zum Raum), `MemoryResultList` (Sortierung + Verdichtung + die Verknüpfungs-Ansicht daneben + höfliche Live-Region), `SearchResultCard` (Quelle formcodiert, Relevanz als Stärke/Position, maskierter Auszug + `#hex6`-Autor, graceful Querlinks B/D), `ResultCluster` (aufklappbare Verdichtung), `RelationView` (kompakte Beziehungsdarstellung, KEIN Graph), `SourceGlyph`, `RelevanceMark`, `MemoryView` (Orchestrator, Rollen-Split + On-Demand-Phasen ohne bedingte Hooks). Die Befehlsleiste (`components/shell/command-palette.tsx`) übergibt jede Eingabe als Suche an `/memory?q=…`.
- Route: `app/(app)/memory/page.tsx` (`requireSection("H")`, nimmt den Deep-Link `?q=` auf).

**Warum so?**
- Paraphrase-Disziplin am schärfsten (Studie §0/§4H): H zeigt das Gedächtnis nach außen — darum erscheint im sichtbaren UI kein Wort aus dem Innenleben (kein Verfahrens-/Bibliotheks-/Substrat-Begriff). Ein eigener Test (`hidden-term.test.tsx`) scannt den gerenderten Text — das strengste Gate der Serie. Ehrlichkeit der Nähe: das Backend liefert keinen Score, also ist die POSITION das Signal — eine Prozentzahl wäre Scheingenauigkeit. Ehrlichkeit der Herkunft: die Suche ist Abruf echter vergangener Notizen, keine Generierung → `ProvenanceStamp` ohne KI-Kennzeichnung. Verdichtung und Verknüpfung nur so weit, wie der F-SEM-Vertrag trägt (nur Schichtnotizen, keine Auflösung/Klasse) — alles darüber graceful markiert, nichts erfunden. HITL hart: H zeigt und navigiert, keine Aktorik. Sitzt vollständig auf FE1 + dem On-Demand-Muster aus E auf und dupliziert nichts (GROUND_TRUTH §21.12).

### Sektion J — Eingabe & Erfassung (`frontend/lib/capture/`, `frontend/components/capture/`, `frontend/app/(app)/capture/`)

Der Werker-Input-Kanal und die Quelle des Gedächtnisses: was hier erfasst wird, taucht später in der Maschinen-Historie (B), den Ereignisketten (D) und der Suche (H) wieder auf. Dritte [KERN]-Sektion. Leitfrage: "Wie bekomme ich, was ich gerade sehe, in unter 15 Sekunden korrekt zugeordnet ins System?" Voller Vertrag: GROUND_TRUTH §21.13.

**Was ist es / wo sitzt es?**
- Reine, transport-agnostische Logik in `lib/capture/`: `submit.ts` (`buildNotePayload` formt den Entwurf in den realen POST-Body, leere Felder weggelassen; `classifyStatus` trennt harte von transienten Fehlern; `submitNote` kapselt den fetch, wirft nie nach außen), `outbox.ts` (die Offline-Schreib-Queue über `localStorage` — `enqueueNote`/`removeFromOutbox` mit dem Datenschutz-Hebel "Lösch-nach-Senden": Klartext liegt nur bis zum erfolgreichen Senden), `sync.ts` (`deriveSyncState` + `syncStatusText` — Hallensprache, "wartet auf Netz" ist normal, kein Alarm-Rot), `scope.ts` (auswählbare Maschinen als UX-Filter aus `assigned_machine_ids`/`assigned_line_ids` — KEINE AuthZ-Grenze, der POST ist serverseitig nicht scope-gefiltert), `classification.ts`/`shifts.ts` (die Kategorie- und Schicht-Optionen als reine Frontend-Konvention), `roles.ts`, `url.ts`. Dazu die Hooks `use-create-note` (online → POST, offline/transient → puffern, hart → melden), `use-outbox` (flusht die Queue beim Netz-Übergang, reentry-geschützt), `use-machines` (lädt + scope-filtert, fünf Zustände) und `use-context-suggestions` (dezente Brücke zu H — Opt-in, ohne Klartext-Cache).
- `components/capture/`: `CaptureForm` (einspaltig, Freitext ZUERST, dann vorausgefüllte Zuordnungs-Chips Maschine/Schicht, dann `CategoryButtons`, unten der große Speichern-Button ≥ 64 px; Sync-Status + Bestätigung mit Rückfluss-Hinweis), `CategoryButtons` (große, MEHRKANALIG kodierte Kategorie-Buttons — Farbfläche + Glyph + Label + aria-pressed, kein Dropdown), `MachineSelect` (Chips, fünf Zustände), `VoiceCapturePlaceholder` (Spracheingabe als markiertes [VISION]-Zielbild — bewusst NICHT interaktiv, kein Fake-Mikrofon), `ContextSuggestions` (frühere Fälle an dieser Maschine — Opt-in, wegklappbar, `ProvenanceStamp` ohne KI-Kennzeichnung — Abruf, keine Generierung; der Entwurf geht nur auf bewusste Geste als Such-Query raus, §8-Datensparsamkeit), `SyncStatus`, `CaptureView` (Orchestrator, Rollen-Split ohne bedingte Hooks). `QuickCaptureFab` (Shell) ist kontextbewusst (auf einer Maschinen-Detailseite → `?machine=`); die Alarmzeile (C) verlinkt mit Maschinen-Kontext nach J.
- Route: `app/(app)/capture/page.tsx` (`requireSection("J")`, liest die Kontext-Vorauswahl `?machine=` wie `/memory` das `?q=`).

**Warum so?**
- Minimale Reibung als oberstes Ziel (Studie §4J): ein Werker mit Handschuhen, wenig Zeit — Freitext zuerst, Maschine/Schicht durch Kontext-Vorbelegung minimiert, ein großes Absenden. Offline-Toleranz ist nicht Beiwerk, sondern der fünfte Zustand: bricht das Netz, bleibt das Formular voll funktionsfähig, die Notiz geht in die lokale Queue, der Sync-Status sagt ruhig "wird gesendet, sobald online", und nach erfolgreichem Senden wird der lokale Klartext gelöscht (Datenschutz §8 — das Frontend hält keinen die serverseitige NER-Maskierung umgehenden Cache). HITL hart: eine Notiz erfassen ist eine menschliche Daten-Eingabe — der einzige Schreibpfad geht an `POST /api/v1/worker_notes`, nie an eine Anlagen-Aktorik. Pseudonymisierung (`author`-HMAC) und Text-Maskierung passieren serverseitig; das UI macht das transparent ("Namen werden vor dem Speichern automatisch geschützt"), ohne dem Werker Arbeit aufzubürden. Ehrlichkeit gegen den realen Vertrag: die Kategorie wird mehrkanalig erfasst und im POST mitgesendet, aber das heutige `WorkerNoteCreate`-Schema nimmt `classification` noch nicht an (markierter Anschlusspunkt, §21.13) — kein FE-Fake, sobald das Backend nachzieht wirkt es ohne Frontend-Änderung. Die Spracheingabe ist als Zielbild gekennzeichnet, nie vorgetäuscht. Sitzt vollständig auf FE1 + dem On-Demand-Muster + der H-Suche auf und dupliziert nichts.

### Sektion A — Flotten-Cockpit (`frontend/lib/cockpit/`, `frontend/components/cockpit/`, `frontend/app/(app)/overview/`)

Die oberste Übersichtsebene und das Landing für Manager/Schichtleiter — die erste [VISION]-Sektion, gebaut auf ihren voll baubaren Werk-/Linien-Kern. **Löst den FE1-Übersicht-Durchstich ab**: `views/overview/` entfernt, die Route `/overview` rendert jetzt das volle Cockpit (erweitert, dupliziert nicht). Leitfrage: „Wo in der Flotte brennt es — und wo bahnt sich etwas an?" Voller Vertrag: GROUND_TRUTH §21.14.

**Was ist es / wo sitzt es?**
- Reine, transport-agnostische Logik in `lib/cockpit/`: `deviation.ts` (Zell-Kodierung aus dem realen `/overview`-Vertrag — da das Backend HEUTE keinen kontinuierlichen Drift-Score liefert, wird die Abweichungs-Intensität ehrlich aus `open_by_severity` + `status` abgeleitet: ein sauberer 1:1-Ladder info→1 … emergency→5 mit Drift-Floor; markierter Anschlusspunkt, sobald F4 einen Score persistiert), `matrix.ts` (Gruppierung primär nach Maschinenklasse × Maschine mit STABILER Ordnung → Live-Updates aktualisieren Zellen in-place ohne Layout-Sprung; markiert systematische Klassen-Drift, wenn die Mehrheit einer Klasse driftet), `kpis.ts` (Aggregate über den scope-gefilterten Satz + ruhige Zustands-Rampen), `history.ts` (reiner Ring-Puffer für die KPI-Sparklines + Trend — die Live-Spur dieser Sitzung, ehrlich kein Backend-Fenster), `priority.ts` (die 3–5 dringendsten Einstiege nach Dringlichkeit mit ihrem realen Querlink-Ziel), `palette.ts`/`flip.ts`/`grid-nav.ts` (Token-Abbildung der Zelle, Kipp-Erkennung, reine Roving-Tabindex-Logik), `scope.ts`/`url.ts` (Föderations-Scope als Client-Filter + reale Querlink-/Scope-URLs). `palette.test.ts` MISST den Kontrast statt zu raten.
- `components/cockpit/`: `DriftHeatmap` (das Herzstück — ein maßgeschneidertes, token-getriebenes SVG wie B's `TimeSeriesChart`, KEINE Charting-Lib; Zeilen = Klassen, Spalten = Maschinen; mehrkanalig: entsättigte sequenzielle Füllung (`heatmap-1..5`) + haloed Schraffur (Richtung, farbunabhängiger Winkel) + haloed FCSM-Buchstabe (auf jeder Füllung lesbar) + Position + aria-Label; **severity-frei in der Fläche**; Klick/Enter → Maschine (B); Roving-Tabindex-Tastaturnav; Mini-Vorschau als Live-Region — kritisch assertiv; Kipp-Puls einmalig), `HeatmapLegend`, `CockpitKpiRow` (drei `KpiTile` aus den Aggregaten, nie nackt; antippbar → Alarme C), `CockpitScopeBar` (`ScopeBreadcrumb` Flotte ▸ Klasse ▸ Linie + Mehr-Werk-Föderation als dezent markiertes Zielbild), `PriorityColumn` („braucht Blick jetzt", reale Querlinks B/C/E), `CockpitView` (Orchestrator, Rollen-Split ohne bedingte Hooks).
- Route: `app/(app)/overview/page.tsx` (`requireSection("A")` blockt Werker/Techniker, liest den Scope aus `?class=&line=`, SSR-Snapshot als Erstbild → WS-Live über das Thema `overview`).

**Warum so?**
- Ein Cockpit zeigt viele Zellen gleichzeitig — genau hier ist die ISA-101-Ruhe die härteste Prüfung. Die Antwort ist konsequent entsättigt: die Heatmap-Fläche trägt NUR die sequenzielle Intensitätspalette (kein Regenbogen, Reihenfolge perzeptuell erhalten, gegen Farbsehschwäche gemessen), Severity-Farbe erscheint ausschließlich in der KPI-Zeile und der Prioritätsspalte, die Heatmap ist die einzige dominante Akzentfläche (~60 %), und Normalbetrieb-Zellen treten zurück (Grundfläche, kein Buchstabe) — nur Auffälliges sticht, kein Ampel-Mosaik. Mehrkanaligkeit ist Pflicht (§5.8): der haloed FCSM-Buchstabe (fg-primary mit neutralem Strich) ist der garantierte farbunabhängige Kind-Kanal — auf JEDER Intensität ≥ 4:1 gemessen —, die Schraffur (ebenfalls haloed) verstärkt ihn besonders auf den hellen Zellen. Ehrlichkeit gegen den realen Vertrag: das Backend hat HEUTE keinen Drift-Score und kein line:/class:-Live-Thema → die Intensität ist die offene-Alarm-Heuristik (markierter Anschlusspunkt) und der Klassen-/Linien-Scope ist ein reiner Client-Filter über das bereits serverseitig scope-gefilterte `/overview` (kein Re-Abo, per Vertrag kein Live-Event). Föderierte Mehr-Werk-Aggregation und die WebGL-Heatmap für sehr große Flotten sind klar als Zielbild gekennzeichnet — bespoke SVG ist für den realen, kleinen Bestand gebaut, nicht vorgetäuscht. HITL hart: das Cockpit zeigt und navigiert, es schaltet nichts; jeder Querlink führt in eine REALE Sicht (Zelle → B, kritisch → C, Drift/Risiko → E). Sitzt vollständig auf FE1 + dem Durchstich-State auf und dupliziert nichts.

### Sektion D — Ereignisketten (`frontend/lib/event-chains/`, `frontend/components/event-chains/`, `frontend/app/(app)/insights/chains/`) + F-REC-Backend-Erweiterung (`src/foreman/reasoners/event_chain/`)

Die rekonstruierte Erzählung entlang der Zeit um einen **Anker-Alarm** — der Bruch, den 4.0-Dashboards strukturell nicht machen: die Zeitachse als Erzählraum, belegte Ereignisse und rekonstruierte Erzählung **hart getrennt**, klassenübergreifend zu Schwestermaschinen. Voller Vertrag: GROUND_TRUTH §21.15 (+ §14.5 Backend).

**Was ist es / wo sitzt es?**
- **Backend (F-REC-Erweiterung):** die in `reconstruct` ohnehin berechnete `EventChain` wird jetzt ausgeliefert UND als eingefrorener JSONB-Snapshot persistiert (`reasoner_explanations.chain_snapshot`/`siblings_snapshot`, Migration 0009, nullable). `POST /reconstruct` + `GET /explanations/{id}` antworten mit `ReasonerExplanationDetailRead` (Superset + `chain` + `siblings`); neuer `GET /explanations/{id}/siblings`. Schwester-Referenzen kommen EHRLICH aus realen NEXUS-Recall-Treffern (`recall.py` zieht optionale strukturierte Metadaten je Treffer; der Service löst Maschinenklasse + jüngste Schwester-Erklärung aus echten DB-Zeilen auf) — Ziele `null`, wenn nicht auflösbar; leerer Recall → leere Liste. Der Output-Guard bleibt unangetastet.
- Reine, transport-agnostische Logik in `lib/event-chains/`: `types.ts` (trennt BELEGT-Knoten von ERZÄHLT-Segmenten), `symbols.ts` (event_type → formcodiertes Symbol konsistent mit B; Hidden-Term: „Abweichungs-Alarm" statt „Drift"), `narrative.ts` (zerlegt die Erzählung an `[source_id]`-Zitaten → Quell-Chips), `timeline.ts` (`buildNodes` + die reine Kopplungs-Funktion `coupledHighlight` für gekoppeltes Hervorheben + reine Roving-Tastatur `nextRovingIndex`), `confidence.ts` (verbale Stufe, nie Prozent), `siblings.ts` (Geschwister-Mapping, navigierbar nur mit realem Ziel), `view-model.ts` (`assembleChainCard`: Belegt/Erzählt-Split, graceful ohne Snapshot, defensiver Fehler-Zustand; `toSummary` für den Manager), `roles.ts`, `url.ts`, `pin.ts` (Pin-Store mit injizierbarem Storage + eingefrorenem Stand), `use-chains.ts` (On-Demand-Trigger, erbt den geteilten Reducer), `use-saved-chains.ts` (Liste + Detail als DataState).
- `components/event-chains/`: `TimelineNarrative` (das Herzstück — zweispaltig: links `TimelineColumn` mit bespoke SVG-`ChainSymbol`-Knoten und Roving-Tastatur, rechts `NarrativePanel` mit „rekonstruiert"-Kennzeichnung, Hypothese-Badge, verbaler Konfidenz, sichtbar geflaggten Inhalten und Quell-Chips; gekoppeltes Hervorheben Knoten ↔ Chip; mobil gestapelt), `ChainSymbol` (bespoke token-getriebenes SVG, KEINE Lib), `EventNode`, `SiblingChains` (klickbar nur bei realem Ziel; leer → kein Block), `PinChainAction`, `ChainTriggerPanel`, `SavedChainsList` (fünf Zustände), `ChainsAggregate` (Manager: ein Satz + Kennzahl), `ChainsView` (Orchestrator, Rollen-Split ohne bedingte Hooks).
- Route: `app/(app)/insights/chains/page.tsx` (`requireSection("D")`, liest `?anchor`/`?machine`/`?explanation` server-seitig). Querlinks REAL: C-`AlarmRow` → `/insights/chains?anchor=`, B-`MachineCrossLinks` → `/insights/chains?machine=`, Hub-Eintrag D live. Additiv in B: `components/machine/pinned-chains.tsx` zeigt angepinnte Ketten mit eingefrorenem Stand.

**Warum so?**
- Der **Anker ist ein Alarm** (Vertrag), kein freies Maschine+Fenster — der Einstieg kommt aus C/B, der Schichtleiter triggert. Die **harte Trennung belegt/erzählt** ist die D-Form der Ehrlichkeits-Haltung: links die belegten Ereignisse (untrusted Werkernotizen sichtbar als unsicher), rechts die als „rekonstruiert" gekennzeichnete Erzählung mit Hypothese-Markierung, verbaler Konfidenz (nie Prozent) und sichtbar gemachten unbelegten Inhalten. Die **Momentaufnahme friert ein** (JSONB-Snapshot, „Stand X") — ein Re-Fetch leitet nicht neu ab, sonst verschöbe sich die gezeigte Kette still, wenn sich Quelldaten ändern. **Schwesterketten sind ehrlich**: nur was der reale Recall hergibt, mit klickbarem Sprung NUR bei real existierender Ziel-Erklärung — keine erfundenen Geschwister, kein Fake-Leerzustand. **ISA-101-Ruhe**: keine Severity-Farbe in der Erzählung (die lebt am verlinkten Original-Alarm in C), dezente Verbindungslinien zeigen zeitliche Folge, nicht Kausalität (die bleibt F vorbehalten). **HITL hart**: D liest, triggert, verknüpft, pinnt — schaltet nie. **Gedächtnis paraphrasiert**: „Abweichung" statt Drift, keine internen Verfahrensnamen im Bedien-Wording (eigener Hidden-Term-Test). Erbt das geteilte On-Demand-Muster aus E ungekürzt (Reducer, Trigger, benannter Zustand, `ProvenanceStamp`) — „erklärte Erkenntnis" bleibt ein wiederkehrendes Muster.

### Sektion I — Plattform/Audit (`frontend/lib/platform/`, `frontend/components/platform/`, `frontend/app/(app)/platform/`)

Die Plattform sieht sich selbst — im Frontend. Teil 2 der Sektion I auf den fertigen Read-APIs (§22): mit welchen Quellen/Schnittstellen ist FOREMAN verbunden (Topologie), und ist jeder Abruf / jede HITL-Entscheidung nachvollziehbar (Audit-Trail, zugleich AI-Act-/Art.-50-Nachweis-Beleg). Das Zielbild der Designstudie §4I ist ein Multi-System-Mesh und als **[VISION]** markiert; diese Ansicht baut die *ehrlich abgeleitete* Teilmenge — kein erfundener Knoten, kein erfundener Live-Feed. Voller Vertrag: GROUND_TRUTH §21.17.

**Was ist es / wo sitzt es?**
- Reine, transport-agnostische Logik in `lib/platform/`: `types.ts` (FE-Spiegel von `TopologyView`/`TopologyNode`/`AuditEntryRead`), `status.ts` (mehrkanaliges Mapping Verbindungsstatus → Token+Form-Glyph+Wort und Datenrichtung → Pfeil-Form; fremder/leerer Wert → ehrlich „unbekannt"/„keine", nie grün geraten), `topology-view-model.ts` (`assembleTopology` gruppiert reale Knoten, `vision`-Flag hat Vorrang → nie als real; `nodeDetailChips` in Hallensprache), `audit-view-model.ts` (`actor` → `#hex6` via `maskPseudonym`, nie Klartext; `detail` defensiv flach; Backend-Reihenfolge bleibt), `audit-filter.ts` (Filter-State → reale Query-Params, `limit` 1..1000 geklemmt), `url.ts` (BFF-Pfade gegen den generischen Catch-all — kein eigener Proxy-Handler), `roles.ts` (`platformRoleView`), `use-topology.ts` (HTTP-Snapshot + manueller Refresh + `probe`-Toggle), `use-audit.ts` (gefiltert/paginiert, nur im Manager-Zweig gemountet).
- `components/platform/`: `TopologyGraph` (das Herzstück — maßgeschneidertes, token-getriebenes SVG, KEINE Lib; FOREMAN im Zentrum, Eingänge links / Substrat + MCP-Grenze rechts, [VISION]-Knoten in abgesetzter gestrichelter Zone ohne Konnektor; `role="img"` + aria-Label), `TopologyNodeMark` (zugängliche Knoten-Karte, exportiert Status-Glyph + Richtungspfeil), `AuditTable`/`AuditRow` (semantische Tabelle, jüngste zuerst, IDs monospace, rein lesend), `AuditFilters` (Filter + Pagination, bewusstes Anwenden), `PlatformView` (Orchestrator, Rollen-Split ohne bedingte Hooks; Tabs per Roving-Tabindex). Route: `app/(app)/platform/page.tsx` (`requireSection("I")`).

**Warum so?**
- **Verbindungsstatus ≠ Maschinenzustand**: der Backend-Status (`verbunden`/`gestört`/`inaktiv`/`unbekannt`) ist NICHT das NE-107-FCSM des Atoms `StatusIndicator` (das kein „unbekannt" kennt) — ein eigener mehrkanaliger Status (Farbe-Token + Form-Glyph + Wort) trägt ihn typsicher und ehrlich, `unbekannt` bleibt neutral (nie grün geraten), ein gestörter Konnektor ist klar aber ruhig (kein Alarm-Rot, ISA-101). **Topologie ehrlich**: nur was das Backend liefert; `simulation` als interne Quelle markiert; die [VISION]-Systeme (ERP/Energie/ext. Sim) in einer abgesetzten, nie verbundenen Zone — kein erfundener Knoten. **Kein WS-Live-Feed** für Sektion I (der „Live-Statuswechsel" der Studie ist [VISION] ohne Push) → HTTP-Snapshot + bewusster, manueller Refresh; die Substrat-Live-Probe schreibt einen Smoke-Marker, darum ist sie als `probe`-Toggle abschaltbar. **Audit unveränderlich-lesend**: `actor` erscheint ausschließlich pseudonym (`#hex6`), nie als Klartext, nie „aufgelöst" (Re-Identifikation lebt im QM-System, §8); keine Edit-/Quittier-Aktion (der Audit protokolliert, löst nichts aus, HITL hart). **Rollen-Split = Sichtbarkeit ≤ Server-Guard**: Manager Topologie + Audit (Tabs), Schichtleiter NUR Topologie — sein Komponentenzweig mountet den Audit-Hook nie, der FE ruft `/api/v1/audit` für ihn gar nicht auf (gäbe 403); Werker/Techniker landen am `requireSection`-Guard. **AI-Act**: die Audit-/Topologie-Sicht ist selbst kein KI-Output → keine KI-Kennzeichnung. **Hidden-Term**: das Substrat heißt außen nur „Gedächtnis-Substrat" (eigener `hidden-term.test.tsx`). Bewusste, am realen Code belegte Abweichungen vom Prompt: eigener Connection-Status statt FCSM-Zwang; generischer BFF-Catch-all statt eigener Proxy-Routen; `ACCESS_MATRIX.I` + Nav-Eintrag bereits beim Fundament angelegt; kein E2E (Vitest-Abdeckung wie §21.8). Adversariale 6-Dimensionen-Review (Workflow) bestätigte alle Haltungen; drei a11y-Befunde gefixt.

### Beispiel-Schablone (zum Kopieren pro neuem Modul)

```
### <Modulname>

**Was tut es?**
…

**Warum existiert es / wo sitzt es?**
…
```

## I — Audit-Trail & Topologie-Quelle (Sektion I, Backend · Teil 1)

> **Die Plattform sieht sich selbst — ehrlich.** Sektion I macht zwei Dinge sichtbar: WER/welches System hat WANN welche Erkenntnis abgerufen oder welche HITL-Entscheidung getroffen (Audit-Trail, zugleich AI-Act-/Art.-50-Nachweis-Beleg), und mit welchen Quellen/Konsumenten FOREMAN verbunden ist (Topologie). Das Zielbild der Designstudie §4I ist ein Multi-System-Mesh und als **[VISION]** markiert; dieser Teil baut die *ehrlich abgeleitete* Teilmenge — kein erfundener Knoten, kein erfundener Akteur. Voller Vertrag: GROUND_TRUTH §22.

### Unveränderliches `audit_logs` (Migration 0010)

**Was tut es?**
Erweitert das nackte `audit_logs`-Skelett (id/user_id/action/target/created_at) additiv um den echten Trail: `actor` (HMAC-Token, nie Klartext), `actor_role`, `action_type` (CHECK), `target_kind`/`target_id`/`machine_id`, `origin` (CHECK), `detail` (JSONB), `occurred_at`. Ein PL/pgSQL-Trigger `trg_audit_logs_append_only` weist `UPDATE`/`DELETE` ab.

**Warum existiert es / wo sitzt es?**
Ein Audit-Trail, der sich ändern lässt, ist kein Beleg. Die Unveränderlichkeit ist deshalb **DB-seitig** erzwungen (Defense-in-Depth, Vorbild die `failure_*`-CheckConstraints), nicht nur app-seitig. Bewusst kein `TRUNCATE`-Trigger — TRUNCATE feuert keine Row-Trigger, und Test-/Reset-Pfade müssen die Tabelle leeren können. Der Legacy-`user_id`-FK bleibt erhalten, wird aber nicht befüllt: der namentliche Nachweis lebt im QM-System (System of Record), FOREMAN führt nur das Token (§8).

### Writer (`audit/writer.py`)

**Was tut es?**
Ein reiner Zeilen-Bauer (`build_audit_log`: `AuditEntry` → ORM-Zeile, spiegelt `action_type` in die Legacy-`action`-NOT-NULL-Spalte) plus zwei Schreibwege. `record(session, entry)` schreibt IN die übergebene Session (atomar). `emit_mcp_retrieval(...)` schreibt best-effort auf EIGENER Session + Commit und schluckt jeden Fehler (loggt nur).

**Warum existiert es / wo sitzt es?**
Zwei Quellen, zwei Transaktions-Bedürfnisse: die HITL-Quittierung MUSS atomar mit dem Geschäfts-Write sein (eine Quittierung ohne ihren Beleg darf es nicht geben) → in-session. Der MCP-Abruf darf den read-only-Tool-Pfad NIE brechen → eigener Sink, best-effort. Beide bauen dieselbe Zeile.

### Zwei reale Schreibpfade (HITL + MCP)

**Was tut es?**
HITL: die Drift-Quittier-Route (`reasoners/drift/router.py`) schreibt nach dem `flush` einen `hitl_acknowledge`-Eintrag in dieselbe Transaktion. MCP: der Tool-Wrapper `_measured` (`mcp/tools.py`) emittiert im `finally` einen `mcp_retrieval`-Eintrag mit Ziel-Kontext aus dem Abruf.

**Warum existiert es / wo sitzt es?**
Es gibt heute genau zwei reale HITL-/Abruf-Spuren — keine erfundenen. Die Quittier-Route liegt am Drift-Reasoner (nicht in `alarms.py`, das keine Ack-Route hat). Beim MCP ist `_measured` der ÄUSSERE Context-Manager, `_read_session` der innere: beim Block-Exit schließt die read-only-Session zuerst, dann läuft das `finally` — der Audit-Sink öffnet eine eigene Session, die Read-Invariante (I, §17.1) bleibt unangetastet. Der Akteur: `mcp/auth.py` kennt nur EINEN geteilten Token, keine Per-Client-Identität → der `actor` ist ein pseudonymisiertes Single-Consumer-Label, ehrlich genau eine Grenze; per-Client-Attribution ist [VISION].

### Read-API + Topologie (`audit/service.py`, `topology/service.py`, Router)

**Was tut es?**
`GET /api/v1/audit` (gefiltert, paginiert, jüngste zuerst, nur Manager/Admin). `GET /api/v1/topology` leitet die Knoten ehrlich aus realen Quellen ab: Eingänge aus `data_points.source` + jüngster `readings`-Aktivität (simulation als intern), Gedächtnis-Substrat per Live-Smoke-Probe (`?probe=false` abschaltbar), F7-MCP-Grenze gespeist aus den `mcp_retrieval`-Audit-Zeilen. Status nur wo messbar (sonst `unbekannt`, nie grün); benannte Drittsysteme bleiben in einer separaten `[VISION]`-Liste.

**Warum existiert es / wo sitzt es?**
Die Linie quer durch FOREMAN: kein Fake. Eine Quelle ohne jüngste Daten wird `unbekannt`/`inaktiv`, nie verbunden gefärbt. ERP/Energiemanagement/externe Simulationssoftware existieren nicht als Integration → sie stehen ehrlich als Vision, nicht als grüner Knoten. Rollen-Split (Studie-Matrix): Audit nur Manager/Admin; Topologie Manager voll, Schichtleiter nur Verbindungsstatus (sein Datenqualitäts-Thema, kein Audit), Werker/Techniker kein Zugang. Schöne Kopplung: Teil A (Audit) speist Teil B (Topologie-MCP-Aktivität).

### Gates (lokal grün)

mypy strict 0, ruff clean + Format clean. Migration 0010 up/down getestet, Trigger blockt UPDATE/DELETE nachgewiesen (eigene ephemere DB je Lauf, eindeutiger Name). 607 Backend-Tests grün (ohne F-PRED, lokal Windows nativ) + 30 neue Sektion-I-Tests; Coverage ≥ 80 % auf `audit/`/`topology/` + den neuen Routern. MCP-Read-Only-Invariante nachgewiesen (Tool-Pfad mutiert keine Domänendaten; Audit-Sink committet separat). Hidden-Term-Scan über die neuen Außen-Strings sauber.
