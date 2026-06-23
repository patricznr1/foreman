# FOREMAN-Simulations-Szenarien — fachliche Begründung & F4-Validierungserwartung

> Stand Juni 2026 · außentauglich (öffentliches Repo)
> Gegenstand: die Szenario-Dateien unter `src/foreman/adapters/simulation/scenarios/` als **Datengrundlage mit bekannter Wahrheit** — die vier Einzel-Szenarien (§1–§4, Validierung des Drift-Reasoners, Sprint F4) sowie der **Twin-Park "Montagelinie 1"** (§7, Schwester-/Klassen-Park für den Wartungszyklen-Reasoner #4). Dieses Dokument liefert pro Szenario die Story, die fachliche Begründung der Signal- und Drift-Parameter (mit Quellen) und die konkrete Validierungs­erwartung (t\*, Erkennungsfenster, Fehlalarm-Erwartung).
> **Architektur (IP):** Das Langzeitgedächtnis ist ein **externer Dienst hinter einer HTTP-API**; für diese Szenarien irrelevant, keine Substrat-Interna.
> **Querverweise:** Drift-Verfahren & Validierungslogik → [`../research/drift-erkennung-verfahren.md`](../research/drift-erkennung-verfahren.md) (§7); erwartete Feature-Signale → [`../research/ausfallvorhersage-methodenwahl.md`](../research/ausfallvorhersage-methodenwahl.md) (§5).

---

## 0. Schema-Hinweise (vorläufig, mit dem F3-Prompt abzugleichen)

Das verbindliche YAML-Szenario-Schema sollte in `prompts/F3_ingestion_simulation.md` liegen — dieses Prompt **existiert im Repo noch nicht**. Die vier Dateien verwenden daher ein **aus GROUND_TRUTH §5 abgeleitetes, in sich konsistentes Schema**, das beim Schreiben des F3-Prompts als verbindlich übernommen oder abgeglichen werden sollte. Konventionen:

- **Zeit-Offsets** als Dauer-Strings `s/m/h/d` ab `scenario.start` (z. B. `7d`, `16d14h`, `5m`).
- **`drift`-Block je Datenpunkt** erzeugt die Abweichung gegen die bekannte Wahrheit. Drift-Typen entsprechen [`drift-erkennung-verfahren.md`](../research/drift-erkennung-verfahren.md) §7:
  - `ramp` — gradueller, (optional progressiver) Anstieg → Verschleiß;
  - `step` — abrupter Mittelwertsprung;
  - `variance` — Streuungs-/Varianzanstieg ohne Mittelwertshift (z. B. Regelabweichung).
- **`seasonality`** modelliert Schicht-Last (frueh/spaet/nacht) und Wochenende (idle/reduced) — das Saison-Muster, das der Reasoner per Deseasonalisierung/State-Gating herausrechnen muss.
- **`machine_state`** (digital, bool) liefert das Lauf-/Stillstand-Signal für das State-Gating.
- **`ground_truth`-Block** ist die F4-Wahrheit: `t_star`, `expected_detection_window`, `expected_false_alarms`.

**Befund für GROUND_TRUTH §5 (Empfehlung):** Der `measurement_type`-Enum kennt **keinen** Wert für Schwingung. Schwingungs-RMS ist hier auf `measurement_type: signal` mit `unit: mm/s` gemappt. Für die Industrie-Praxis (Vibration ist *das* zentrale Lager-Signal) wäre ein eigener Wert `vibration` (oder `velocity`/`acceleration`) sinnvoll — Vorschlag zur Aufnahme bei der nächsten GROUND_TRUTH-Revision.

Alle vier Dateien sind YAML-valide und gegen die Enums aus GROUND_TRUTH §5 geprüft (`kind`, `measurement_type`, `component_type`, `alarms.severity`, `alarms.category`, `source: simulation`). Werker-`author`/`performed_by` sind **synthetische Pseudonyme** (`PSEUDO_*`), passend zur Pseudonymisierungs-Strategie ([`../research/anonymisierung-werkerdaten.md`](../research/anonymisierung-werkerdaten.md)).

---

## 1. `bearing_drift` — Spindellager-Schaden

**Story.** Eine CNC-Spindel läuft eine Woche gesund, dann beginnt eine Außenring-Schädigung am vorderen Spindellager. Der Schwingungs-RMS steigt über rund zwei Wochen graduell an; die Lagertemperatur folgt erst Tage später. Zwei Schichten vor dem Temperaturalarm dokumentiert ein Werker ein „mahlendes Geräusch“ — die Notiz, die FOREMANs „hatten wir das schon mal“ trägt.

**Fachliche Begründung der Signatur.**

- **Vibration als Frühindikator, Temperatur als Spätindikator.** Die klassische Lager-Degradation verläuft in Stufen: zuerst hochfrequente/ultraschall-Signale, dann Anstieg im Hüllkurven-/Resonanzbereich, dann Lagerschadenfrequenzen im Geschwindigkeitsspektrum mit steigendem Breitband-RMS, zuletzt starker RMS-Anstieg **mit Temperaturanstieg** und drohendem Ausfall. Die Temperatur steigt also **spät** — ihr Alarm kommt, wenn der Schaden bereits fortgeschritten ist. Genau das bildet das Szenario ab: `vib_rms`-Drift ab t\*=7 d, `bearing_temp`-Drift erst ab 15 d.
- **Magnituden nach ISO 20816 (Nachfolger ISO 10816).** Schwingstärke wird über den RMS der Schwinggeschwindigkeit (mm/s, 10–1000 Hz) in Zonen A–D bewertet. Gesund liegt im Bereich Zone A/B (hier 1,8 mm/s); der Ramp auf ~7 mm/s führt über Zone C in Zone D (unzulässig/schädigend). `normal_max: 4.5` markiert grob die B/C-Grenze einer mittelgroßen Maschine.
- **Zeithorizont.** Von der ersten im RMS sichtbaren Veränderung bis zum Ausfall liegen typischerweise Tage bis Wochen (P-F-Intervall der RCM-Lehre). Der gewählte Verlauf (t\*=7 d, kritisch ~20 d) ist ein realistisch komprimierter, aber plausibler Ausschnitt.
- **Stromsignal** steigt leicht mit (höhere Reibung → minimal höhere Stromaufnahme) — als schwaches Mitsignal modelliert (ab 12 d, +1,8 A).

**Drift-Parameter.** Primär `vib_rms`: `ramp`, t\*=7 d, +5,2 mm/s, leicht progressiv (Verschleiß beschleunigt). Bezug zu §5 des Ausfallvorhersage-Docs: Roll-RMS/-Mittel und Trend/Slope sind genau die Features, die diesen Verlauf greifbar machen.

**F4-Validierungs-Erwartung.** Der Drift-Reasoner soll die Vibrations-Drift im **Erkennungsfenster 7–10 d** melden — also Tage **vor** der Werker-Notiz (~16 d) und **vor** dem Temperaturalarm (~17 d). `expected_false_alarms: 0`. Erfolgskriterium ist nicht nur „erkannt“, sondern „**früh** erkannt“.

---

## 2. `tool_wear` — Werkzeugverschleiß (CNC-Spindel)

**Story.** Ein frisch eingewechselter Schaftfräser altert über mehrere Tage Zwei-Schicht-Betrieb. Spindel-Drehmoment und Motorstrom steigen monoton mit dem Flankenverschleiß; gegen Standzeitende beschleunigt der Anstieg, und die Ist-Drehzahl beginnt unter Last zu „zittern“. Der Werker bemerkt den Verschleiß erst spät an Oberfläche und Spanfarbe.

**Fachliche Begründung der Signatur.**

- **Last/Strom ∝ Schnittkraft ∝ Flankenverschleiß.** Mit zunehmendem Flankenverschleiß (VB) steigen die Schnittkraftkomponenten; Spindel-Leistung, -Strom und -Moment sind etablierte, empfindliche Indikatoren der Werkzeug-Verschleißstufe. Der Motorstrom bildet das Schnittmoment gut ab (in Studien mit wenigen Prozent Schätzfehler). Daher hier **Drehmoment** als Primärsignal und **Strom** als redundantes Lastsignal — beide `ramp` ab t\*=2 d (nach Werkzeug-Einlauf).
- **Progressiver Verlauf.** Flankenverschleiß wächst zunächst moderat und beschleunigt gegen Standzeitende (überproportionaler VB-Anstieg) — abgebildet durch `shape: progressive`.
- **Regelabweichung als spätes Varianz-Signal.** Bei hoher Last/zunehmendem Verschleiß steigt die Streuung der Ist-Drehzahl um den Sollwert. Das ist kein Mittelwertshift, sondern ein **Varianz**-Effekt → Drift-Typ `variance` (ab 7 d, Streuung ×4). Damit deckt das Szenario bewusst einen Drift-Typ ab, den ein reiner Mittelwert-Detektor (z. B. ADWIN auf dem Rohmittel) schwächer sieht — ein guter Test für die Verfahrenswahl aus §7 des Drift-Docs.
- **Abgrenzung zu `bearing_drift`.** Anderes Bauteil (spindle statt bearing), andere Signatur (Last/Strom statt Vibration/Temperatur), andere Ursache. Das zwingt den Reasoner, nicht auf ein einzelnes Signal zu überfitten.

**F4-Validierungs-Erwartung.** Primär `spindle_torque`: Erkennung im Fenster **2–4 d**; Strom als redundante Bestätigung; die Drehzahl-Varianz ab 7 d als zusätzlicher, späterer Treffer. `expected_false_alarms: 0`. Werker-Wahrnehmung erst ~8 d → erneut der Frühwarn-Mehrwert.

---

## 3. `lubrication_correlation` — Schmierstoff-Wahl & Folge-Degradation

**Story.** Zwei baugleiche Lager derselben Maschine werden am selben Tag nachgeschmiert — Lager A spezifikationskonform (Schmierstoff X), Lager B mit ungeeignetem Ersatzfett (Y). In den Wochen danach bleibt Lager A stabil, Lager B degradiert deutlich schneller. Eine Werker-Notiz hält die Ersatz-Schmierung fest; eine spätere Notiz bemerkt, dass die Abtriebsseite wärmer/lauter läuft. Das ist die kausale Story für die spätere **Wartungszyklen-Analyse**: nicht „ob geschmiert“, sondern „**womit**“.

**Fachliche Begründung der Signatur.**

- **Schmierstoff bestimmt die Lagerlebensdauer.** Eine zu niedrige **Grundölviskosität** für die gegebene Drehzahl/Last führt zu unzureichendem Schmierfilm (zu niedrige Viskositätskennzahl κ), Mischreibung und beschleunigter Ermüdung. Gleiche Wartungs*art*, anderer Schmierstoff → andere Degradationsrate. Modelliert: Lager B `vib_rms_b` `ramp` ab t\*=3 d (+4,8 mm/s, progressiv), Lager A nur leichte normale Alterung (+0,6 mm/s).
- **Temperatur folgt** auch hier spät (Lager B ab 12 d) — gleiche Spätindikator-Logik wie in `bearing_drift`.
- **Kontroll-Lager.** Lager A ist die eingebaute Negativkontrolle: gleiche Maschine, gleiches Alter, gleiche Belastung, nur korrekt geschmiert → darf **nicht** als Drift gemeldet werden.
- **`maintenance_events`** trägt die kausale Ankerinformation (zwei Schmierungen, X vs. Y, mit Beschreibung und pseudonymem Ausführer). Voraussetzung: die F3-Engine unterstützt `maintenance_events` — im F3-Prompt nachzuziehen; die YAML-Struktur ist hier bereits sauber angelegt.

**F4-Validierungs-Erwartung.** Drift **nur** an `vib_rms_b`, Erkennungsfenster **3–7 d**; `vib_rms_a` ist Kontrolle (keine Meldung). `expected_false_alarms: 0`. Über F4 hinaus liefert das Szenario die Vorlage für die Wartungszyklen-Analyse (Korrelation Wartungsereignis → Folge-Degradation).

---

## 4. `healthy_baseline` — gesunde Maschine, kein Drift (Fehlalarm-Test)

**Story.** Dieselbe Maschinen-/Sensorstruktur wie `bearing_drift`, aber zehn Tage völlig gesund: ausgeprägte Schicht-Saisonalität und ein Wochenende mit Stillstand. Keine Degradation.

**Fachliche Begründung.** Industrielle Sensordaten sind **aus betrieblichen Gründen** nicht-stationär: Last-, Temperatur- und Stromprofile unterscheiden sich systematisch zwischen Früh-/Spät-/Nachtschicht, und am Wochenende steht die Maschine. Ein Drift-Detektor, der **auf dem Rohsignal** läuft, würde jeden Schichtwechsel und jeden Anlauf als „Drift“ melden (siehe [`drift-erkennung-verfahren.md`](../research/drift-erkennung-verfahren.md) §3). Dieses Szenario prüft daher genau die vorgelagerte **Deseasonalisierung + State-Gating**: Nur wenn der Reasoner das Saison-Muster herausrechnet und Stillstände ausblendet, bleibt er hier still.

**F4-Validierungs-Erwartung.** `drift_present: false`, `expected_drift_detections: 0`, `expected_false_alarms: 0`. Konkrete Negativtests: Schichtwechsel (Last-/Temperatursprünge) und Wochenend-Stillstand dürfen **nicht** als Drift/Anomalie gemeldet werden. **Jede** Meldung auf diesem Szenario ist ein Fehlalarm und ein F4-Abnahme-Fehlschlag. Damit ist `healthy_baseline` die unverzichtbare Negativkontrolle zu den drei Positiv-Szenarien.

---

## 5. Zusammenfassung der F4-Validierungsmatrix

| Szenario | Primärsignal | Drift-Typ | t\* | Erwartetes Erkennungsfenster | Fehlalarm-Erwartung |
|---|---|---|---|---|---|
| `bearing_drift` | `vib_rms` (mm/s) | ramp (progressiv) | 7 d | 7–10 d | 0 |
| `tool_wear` | `spindle_torque` (Nm) | ramp (progressiv) | 2 d | 2–4 d | 0 |
| `lubrication_correlation` | `vib_rms_b` (mm/s) | ramp (progressiv) | 3 d | 3–7 d | 0 (Lager A = Kontrolle, keine Meldung) |
| `healthy_baseline` | — | kein Drift | — | keine Detektion | 0 (jede Meldung = Fehlschlag) |

Gemeinsamer roter Faden: In allen drei Positiv-Szenarien erkennt der Drift-Reasoner die Veränderung **Tage vor** der menschlichen Wahrnehmung bzw. dem klassischen Schwellwert-Alarm — das ist der nachzuweisende Frühwarn-Mehrwert. `healthy_baseline` belegt, dass dieser Mehrwert nicht durch Fehlalarme erkauft wird.

---

## 6. Offene Punkte

- **F3-Schema-Abgleich:** Beim Schreiben von `prompts/F3_ingestion_simulation.md` das hier verwendete Schema als verbindlich übernehmen oder die YAMLs daran anpassen (insb. `drift`-Block-Felder, Offset-Notation, `maintenance_events`-Unterstützung).
- **`measurement_type: vibration`** in GROUND_TRUTH §5 ergänzen (derzeit `signal`/`mm/s`-Workaround).
- **Werker-Notiz-Stil:** Notiz-Texte am Stilguide (`werker-notizen-stilguide.md`) ausrichten; aktuell knappe, plausible deutsche Schichtbericht-Notizen.
- **Parametrierung an Realdaten:** Magnituden und Zeithorizonte sind fachlich plausibel, aber synthetisch; sobald reale SPS-/Sensordaten vorliegen, gegen sie kalibrieren.
- **Erkennungsfenster vs. Detektor-Parameter:** Die Fenster (z. B. 7–10 d) sind mit den Warm-up-/`delta`-Startwerten aus dem Drift-Doc (§6) konsistent zu halten; bei Tuning beidseitig nachziehen.

---

## 7. Twin-Park "Montagelinie 1" — Schwester-/Klassen-Park (Schritt 1)

Über die vier Einzel-Szenarien hinaus liefert der Park einen **Schwester-/Klassen-Vergleich**: mehrere Instanzen je Maschinenklasse, als Linie angeordnet. Er ist die Datengrundlage für den Wartungszyklen-Reasoner (#4, noch offen) und den Klassen-Drift-Vergleich. Magnituden und Degradationssignaturen sind — wie bei den vier Einzel-Szenarien — fachlich begründet (Quellen unten), die Werte sind synthetisch.

**Bau ohne Schema-Änderung.** Ein Park entsteht aus **N Einzelmaschinen-Szenariodateien mit gleicher `line.label`** (`"Montagelinie 1"`), verschiedener `machine.external_id` und gleicher `machine_class` für Schwestern. `seed.py` schlüsselt die Linie auf `label` → alle 12 Maschinen hängen an **einer** Linie; der Schwester-/Klassen-Vergleich passiert maschinenübergreifend in der DB. Gemeinsame Zeitachse: `start: 2026-06-01T06:00 (+02:00)`, `duration: 21d`, `sample_interval: 10m`. Dateien: `src/foreman/adapters/simulation/scenarios/park_*.yaml`; Seed der ganzen Linie über `python -m foreman.adapters.simulation.park`.

### 7.1 Park-Layout (12 Maschinen / 5 Klassen)

| external_id | Klasse | Rolle | Datei | Degradation |
|---|---|---|---|---|
| FD-01 | `feeder` | Teilezuführung A, **gesunde Kontrolle** | `park_fd01` | — |
| FD-02 | `feeder` | Teilezuführung B, **D-Ketten-Kopf** | `park_fd02` | B6 Dosis-Streuung + B5 Pneumatik-Schaltzeit |
| PR-01 | `servo_press` | Fügepresse 1 | `park_pr01` | B2 Hydraulik-Leckage |
| PR-02 | `servo_press` | Fügepresse 2, **D-Ketten-Mitte** | `park_pr02` | B1 Werkzeugverschleiß (P2+P4) |
| PR-03 | `servo_press` | Fügepresse 3, **gesunde Kontrolle** | `park_pr03` | — |
| AX-01 | `servo_axis` | Handling-Achse X, **P1-/P3-Kontrolle** | `park_ax01` | — |
| AX-02 | `servo_axis` | Handling-Achse Y | `park_ax02` | B4 falscher Schmierstoff (P1) |
| AX-03 | `servo_axis` | Handling-Achse Z (vertikal) | `park_ax03` | B3 Lager-Drift durch Überlast |
| AX-04 | `servo_axis` | Handling-Achse U, **gesund/über-gewartet** | `park_ax04` | — (P3) |
| RB-01 | `robot` | Bestückroboter 1, **gesunde Kontrolle** | `park_rb01` | — |
| RB-02 | `robot` | Bestückroboter 2 (Reserve), **gesund/Duty-Sonderfall** | `park_rb02` | — |
| VS-01 | `vision` | Endkontrolle, **D-Ketten-Endpunkt** | `park_vs01` | reject-Anstieg (Wirkung der Kette) |

**Instanz-Streuung** ohne Schema-Änderung über `baseline.mean`/`noise_std`/`load_factor` je Datei (Fertigungstoleranz, Duty, Einbaulage). Bewusste Sonderfälle für den Eigenprofil-Test (#2): **AX-03** trägt durch die Vertikallage ein erhöhtes Grund-Drehmoment/-Strom — das ist **normal, kein Drift**; **RB-02** läuft nur Früh-/Spätschicht (anderes Duty-Profil, normal). Datenpunkt-Katalog je Klasse: Kraft/Drehmoment/Strom/Temperatur über die `measurement_type`-Enums, Druck/Position/Vibration über `signal`+Einheit, Sollwerte über `kind: setpoint` (konstante Baseline). **Zähler (`counter`) sind bewusst nicht modelliert** — die Engine erzeugt nur State- (`driven_by`) oder Analog-Signale (`mean`); ein monoton zählender Wert ist heute nicht abbildbar und würde als irreführende Konstante erscheinen.

### 7.2 Degradationsfamilien B1–B7

Aufbau auf den vier Einzel-Szenarien (§1–§4), als `drift`-Block (ramp/variance) ausgedrückt:

- **B1 Werkzeugverschleiß** (PR-02): `press_force`/`motor_current`/`ram_position` ramp progressiv ab t\*=4d (∝ Schnittkraft, ISO 8688). Schwestern PR-01/PR-03 gesund.
- **B2 Hydraulik-Leckage** (PR-01): `hydraulic_pressure` ramp ↓ ab t\*=6d, `oil_temp` ↑ spät, `ram_position` ↑ (Kompensation).
- **B3 Lager-Drift / Überlast** (AX-03): `axis_bearing_vibration` ramp progressiv ab t\*=7d (ISO 20816 Zone A→C/D), Temperatur spät — durch Vertikallast, trotz korrekter Wartung.
- **B4 Schmier-Korrelation** (AX-02 vs AX-01): `axis_bearing_vibration` ramp progressiv ab t\*=3d (falscher Schmierstoff Y, ISO VG 46); AX-01 (Fett X) stabil.
- **B5 Pneumatik-Schaltzeit** (FD-02): `clamp_switch_time` ramp progressiv ab t\*=10d (Ventil-/Dichtungsverschleiß).
- **B6 Dosis-Streuung** (FD-02, Ketten-Kopf): `dose_mass` variance + `feed_rate` ramp ↓ ab t\*=4d.
- **B7 Gesund (Negativkontrolle)**: FD-01, PR-03, AX-01, AX-04, RB-01, RB-02 — **kein** `drift`-Block, `drift_present: false`. Jede Drift-/Wartungs-Meldung hier ist ein #2/#4-Abnahmefehler.

### 7.3 D-Kette (Sektion D, F6 on-demand)

Eine durchgehende Kette über drei Dateien, am Betriebstag **Freitag (Tag 4)** gestaffelt — bewusst kein Wochenend-Tag (Stillstand):

`FD-02` Dosis-Streuung (t\*=4d, Notiz 4d13h) → `PR-02` intermittierende Unterfüllung (Werker-Notiz 4d14h — bewusst **kein** Alarm, damit der press_force-Lastalarm der echte Verschleiß-Anker bleibt) → `VS-01` Ausschuss-Anstieg (`reject_rate` ab t\*=4d, Notiz 4d15h, Alarm `REJECT_RATE_HIGH` 4d16h). Strenge zeitliche Ordnung Oberlauf vor Unterlauf.

Die Verbindung ist **zeitliche Folge, keine behauptete Kausalität** — der Ereignisketten-Reasoner (F6) rekonstruiert sie on-demand ab dem VS-01-Anker rückwärts. Mechanisch ist die Kette **kein** Feld einer Datei, sondern emergent aus den Ereignissen mehrerer Maschinen in der DB (Oberlauf-Ereignis früher, Unterlauf-Wirkung später, gleiche `line.label`). Die Unterfüllung an PR-02 ist ein **transientes** Ereignis (Alarm/Notiz), bewusst **nicht** als zweite Drift auf `press_force` modelliert (eine Drift je Datenpunkt; PR-02s `press_force`-Kurve trägt allein den Werkzeugverschleiß).

### 7.4 Wartungs-Kausalmuster P1–P4 (Reasoner #4) — Master-Ground-Truth

Pro Park-Datei trägt der `ground_truth`-Block (`extra=allow`) ein `maintenance_causal`-Feld (Ursache-Ereignis, betroffene Maschine, Kontroll-Schwestern, erwarteter #4-Befund, `expected_false_findings: 0`). Übersicht der eingebauten Muster:

| Muster | Aussage für #4 | Umsetzung | Betroffen | Kontrolle |
|---|---|---|---|---|
| **P1 Schmierstoff-Wahl** | Folge hängt am *Schmierstoff*, nicht am *Ob-geschmiert* | gleiche Wartungsart, Fett Y (VG46) vs X (VG150) | AX-02 | AX-01 |
| **P2 Intervall zu lang → Ausfall** | längeres Wechselintervall korreliert mit Drift/Ausfall | tool_change 90d statt 30d → B1-Drift → tool_failure | PR-02 | PR-01, PR-03 |
| **P3 Intervall zu kurz → Verschwendung** | kürzeres Intervall bringt **keine** Verbesserung | lubrication 7d (3 Events) = identisch gesund wie 30d | AX-04 | AX-01 |
| **P4 Übersprungene Inspektion** | fehlende Inspektion geht dem Ausfall voraus | planmäßige Inspektion ~10d weggelassen (Event-Absenz) | PR-02 | PR-01, PR-03 |

**Ehrlichkeits-Fälle (nicht jede Drift ist Wartungsversagen):** AX-03 (Lager-Drift durch **Überlast**, trotz korrekter Wartung), PR-01 (Dichtung am **Lebensende**, trotz disziplinierter Inspektion), FD-02 (reiner **Verschleiß**). #4 darf diesen Schwestern keinen Wartungsfehler (P1–P4) zuschreiben.

**P5 (Intra-Maschinen-Wartungseffekt / Sägezahn) ist NICHT Teil dieses Schritts.** Das aktuelle Schema kennt nur *eine* monotone Drift je Datenpunkt; „gute Wartung flacht die Driftrate ab“ ist **innerhalb** einer Maschine heute nicht abbildbar (über Schwestern hinweg dagegen schon — genau P1–P4). P5 braucht die Engine-Erweiterung **E1** (mehrphasige Drift / `maintenance_effect`) und ist der nachgelagerte Schritt, ebenso der Reasoner #4 selbst und FE-Sektion F.

### 7.5 Beobachtungsgrenze (hart)

Der **Grund** einer Degradation (falscher Schmierstoff, überfälliges Werkzeug, übersprungene Inspektion) lebt ausschließlich im **Wartungs-Log** (`maintenance_events.description`) und in der **Ground-Truth** (`ground_truth`, unsere verborgene Validierungs-Wahrheit) — **niemals** als gemessener Datenpunkt. FOREMAN „sieht" nur die **Wirkungen** in beobachtbaren Signalen (Vibration, Temperatur, Kraft, Druck, Strom, reject_rate). Die Last-Größen des Parks (Kraft/Drehmoment/Druck/Strom) fallen als beobachtete Datenpunkte an und speisen später die G-Anzeige als Nebenprodukt — kein Simulator. Konsistent mit der #5-/Belastungs-Korrektur.

> Magnituden, Intervalle und Zeithorizonte sind fachlich begründete, **synthetische** Annahmen (ISO 20816/8688, RCM P-F-Intervall, Schmierstoff κ/NLGI/ISO-VG), die finale Echtheits-Abnahme macht Patric (17 Jahre Industrie). Vor Einsatz mit Realdaten kalibrieren.

---

## Quellen

- **ISO 20816** (Nachfolger **ISO 10816**) — Bewertung der Maschinenschwingung über RMS-Schwinggeschwindigkeit (mm/s), Zonen A–D.
- Lager-Degradationsstufen (Vibration als Früh-, Temperatur als Spätindikator) — Condition-Monitoring-Literatur; Vibration-Temperatur-Fusion zur Stufenerkennung (z. B. PMC12349605, 2025) und Degradationsstufen-Modelle (arXiv:2203.03259).
- **P-F-Intervall** / Potential-to-Functional-Failure — Reliability-Centred-Maintenance-Lehre (Moubray, RCM II).
- Werkzeugverschleiß über Spindelstrom/-leistung/-moment (Schnittkraft ∝ VB) — Tool-Condition-Monitoring-Literatur (z. B. ScienceDirect S2212827125001209; arXiv:2212.13905 zu Flankenverschleiß aus Maschinendaten). ISO 8688 (Verschleißkriterien Fräsen).
- Schmierstoff/Grundölviskosität und Lagerlebensdauer (κ-Verhältnis, Mischreibung) — Wälzlager-Schmierungsgrundlagen (Hersteller-Engineering-Literatur).
- Interne Querverweise: [`../research/drift-erkennung-verfahren.md`](../research/drift-erkennung-verfahren.md) §3/§7; [`../research/ausfallvorhersage-methodenwahl.md`](../research/ausfallvorhersage-methodenwahl.md) §5; GROUND_TRUTH §5 (Schema/Enums).

> Hinweis: Signaturen und Zeithorizonte sind fachlich begründete, **synthetische** Annahmen für die Validierung des Drift-Reasoners gegen bekannte Wahrheit — keine Messdaten einer realen Anlage. Vor Einsatz mit Realdaten kalibrieren.
