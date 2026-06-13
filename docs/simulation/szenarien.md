# FOREMAN-Simulations-Szenarien — fachliche Begründung & F4-Validierungserwartung

> Stand Juni 2026 · außentauglich (öffentliches Repo)
> Gegenstand: die vier Szenario-Dateien unter `src/foreman/adapters/simulation/scenarios/` als **Datengrundlage mit bekannter Wahrheit** für die Validierung des Drift-Reasoners (Sprint F4). Dieses Dokument liefert pro Szenario die Story, die fachliche Begründung der Signal- und Drift-Parameter (mit Quellen) und die konkrete Validierungs­erwartung (t\*, Erkennungsfenster, Fehlalarm-Erwartung).
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
- **Werker-Notiz-Stil:** Sobald der Stilguide (Cowork-Auftrag B) vorliegt, die Notizen-Texte daran angleichen; aktuell knappe, plausible deutsche Schichtbericht-Notizen.
- **Parametrierung an Realdaten:** Magnituden und Zeithorizonte sind fachlich plausibel, aber synthetisch; sobald reale SPS-/Sensordaten vorliegen, gegen sie kalibrieren.
- **Erkennungsfenster vs. Detektor-Parameter:** Die Fenster (z. B. 7–10 d) sind mit den Warm-up-/`delta`-Startwerten aus dem Drift-Doc (§6) konsistent zu halten; bei Tuning beidseitig nachziehen.

---

## Quellen

- **ISO 20816** (Nachfolger **ISO 10816**) — Bewertung der Maschinenschwingung über RMS-Schwinggeschwindigkeit (mm/s), Zonen A–D.
- Lager-Degradationsstufen (Vibration als Früh-, Temperatur als Spätindikator) — Condition-Monitoring-Literatur; Vibration-Temperatur-Fusion zur Stufenerkennung (z. B. PMC12349605, 2025) und Degradationsstufen-Modelle (arXiv:2203.03259).
- **P-F-Intervall** / Potential-to-Functional-Failure — Reliability-Centred-Maintenance-Lehre (Moubray, RCM II).
- Werkzeugverschleiß über Spindelstrom/-leistung/-moment (Schnittkraft ∝ VB) — Tool-Condition-Monitoring-Literatur (z. B. ScienceDirect S2212827125001209; arXiv:2212.13905 zu Flankenverschleiß aus Maschinendaten). ISO 8688 (Verschleißkriterien Fräsen).
- Schmierstoff/Grundölviskosität und Lagerlebensdauer (κ-Verhältnis, Mischreibung) — Wälzlager-Schmierungsgrundlagen (Hersteller-Engineering-Literatur).
- Interne Querverweise: [`../research/drift-erkennung-verfahren.md`](../research/drift-erkennung-verfahren.md) §3/§7; [`../research/ausfallvorhersage-methodenwahl.md`](../research/ausfallvorhersage-methodenwahl.md) §5; GROUND_TRUTH §5 (Schema/Enums).

> Hinweis: Signaturen und Zeithorizonte sind fachlich begründete, **synthetische** Annahmen für die Validierung des Drift-Reasoners gegen bekannte Wahrheit — keine Messdaten einer realen Anlage. Vor Einsatz mit Realdaten kalibrieren.
