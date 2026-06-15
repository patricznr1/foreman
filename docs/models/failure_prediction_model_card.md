# Model Card — Ausfallvorhersage-Reasoner (F-PRED)

> **Status:** Methoden-Demonstrator. **`validation_status = simulation_only`** ·
> **`data_regime = simulation`** · **`model_version = lgbm-failure-2026.06`** ·
> Stand 2026-06-15.
>
> Dieses Modell ist **auf Simulationsdaten trainiert**. Seine Pipeline ist technisch
> **verifizierbar**, aber ohne reale Run-to-failure-Historie **nicht validierbar**.
> Der Sim-Vorbehalt ist strukturell erzwungen (Pflichtfeld an jeder Vorhersage,
> Metrik-Label auf allen `foreman_failure_*`-Kennzahlen) — er ist Kern-Deliverable,
> nicht Disclaimer. Die ausführliche fachliche Begründung steht in
> [§7](#7-warum-simulationsdaten-für-eine-ausfallvorhersage-nicht-genügen).

---

## 1. Übersicht

| Feld | Wert |
|---|---|
| Reasoner | Ausfallvorhersage (F-PRED), Reasoner #3 der FOREMAN-Plattform |
| Aufgabe | Binäre Klassifikation: Ausfall innerhalb des Vorhersagehorizonts (ja/nein) |
| Modellklasse | LightGBM (`LGBMClassifier`), Gradient-Boosted Trees |
| Erklärbarkeit | SHAP `TreeExplainer` (exakte Faktor-Attribution) |
| Datenregime | **Simulation** (digitaler Zwilling aus SPS-Logik; keine realen Logs) |
| Vorhersagehorizont | 14 Tage (336 h), global beim Training parametrierbar (`--horizon-days`); maschinenklassen-spezifische Horizonte sind Migrationspfad (§8), im Demonstrator nicht implementiert |
| Vorlauf-Fenster (Features) | 72 h |
| Trainingsquelle | `bearing_drift`, `tool_wear`, `lubrication_correlation` (Ausfall) + `healthy_baseline` (Negativ) |
| Validierung | **nicht möglich** auf diesen Daten (s. §6/§7) |

FOREMAN trainiert **nicht zur Laufzeit**: Das Training ist ein reproduzierbarer
Offline-Schritt (`python -m foreman.reasoners.failure.train`, seedbar); die Inferenz
lädt nur das Artefakt. Der Reasoner **empfiehlt, schaltet nichts** (keine Aktorik,
Human-in-the-Loop).

---

## 2. Verwendungszweck (Intended Use)

- **Architektonischer Platzhalter** für die Ausfallvorhersage in einer
  Reasoning-Plattform: Die Stelle ist sauber besetzt; kommen je echte Daten, tauscht
  man nur das Trainingsset (§8 Migrationspfad).
- **Methoden-Demonstration** für den KI-Track: klassisches ML (LightGBM) + exakte
  Attribution (SHAP) + spätere LLM-Verschränkung (Erklär-Layer, eigener Folgeschritt).
- **Reifezeichen**: ein Modul, das seine eigene Grenze präzise deklariert, ist reifer
  als eines, das Einsatzbereitschaft vortäuscht.

Jede erzeugte Empfehlung ist als **KI-Output** zu kennzeichnen; die Entscheidung
verbleibt beim Operator (AI-Act-Transparenz, HITL).

## 2.1 Nicht-Verwendungszweck (Out of Scope / Misuse)

- **Keine** Verwendung als validierter Prädiktor für reale Instandhaltungs-,
  Sicherheits- oder Budget-Entscheidungen. Die Zahlen sagen über reale Maschinen
  **nichts** aus (§7).
- **Keine** safety-kritische Aktorik. FOREMAN gibt Empfehlungen, schaltet nie.
- Die hohen Eval-Werte (§6) dürfen **nie** als „Genauigkeit der Ausfallvorhersage"
  kommuniziert werden — sie messen Simulator-Rekonstruktion, nicht Realität.

---

## 3. Trainingsdaten

**Quelle.** Vier Simulationsszenarien des FOREMAN-Adapters, abgeleitet aus
SPS-Logik (Steuerprogramm, Register, Sollwerte, Grenzwerte) — **physikalisch
plausible** Degradationsverläufe, kein interpoliertes Rauschen:

- `bearing_drift` — Spindellagerschaden (Vibrations-Ramp ab t\*=7 d, später
  Temperatur), Ausfall ~20 d 11 h.
- `tool_wear` — Werkzeugverschleiß (Last/Strom monoton, späte Drehzahl-Varianz),
  Ausfall ~9 d 12 h.
- `lubrication_correlation` — Schmierstoff-Fehlwahl → beschleunigte Lagerdegradation
  (Lager B), Ausfall ~24 d 6 h.
- `healthy_baseline` — gesunde Maschine, **kein** Ausfall → reines Negativmaterial.

**Label.** Aus `ground_truth.failure` (additiv ins Szenario-Format aufgenommen):
positiv = Bezugszeitpunkt liegt im Vorlauf-Fenster `[failure − H, failure]`
(Ausfall im Horizont *H*), negativ sonst; ausfall-ferne Fenster und alle
`healthy_baseline`-Fenster. Nach dem Ausfall wird nicht mehr vorhergesagt.

**Anti-Leakage.** (1) Features stammen ausschließlich aus Daten mit Zeitstempel
**vor** dem Bezugszeitpunkt (strikt getestet). (2) Der Train/Eval-Split trennt
**disjunkte Läufe** (Szenario/Seed) — Fenster eines Laufs landen nie gleichzeitig in
Train und Eval (kein zeilenweises Mischen).

**Klassenbalance (Artefakt `lgbm-failure-2026.06`).** Train: 369 Samples (222
positiv / 147 negativ), Eval: 123 Samples. Imbalance per `scale_pos_weight =
#negativ/#positiv` (Class-Weights), **kein** SMOTE (verschlechtert die
Wahrscheinlichkeits-Kalibrierung bei Boosting; synthetische Minderheitsdaten nur aus
dem digitalen Zwilling, nicht aus Interpolation).

**Es gibt keinen realen Datenpfad.** Patric erhält aus seinen Industriekontakten
SPS-**Programme**, keine **Logfiles**. Ein SPS-Programm beschreibt, *wie* eine
Maschine funktioniert, nicht *was* ihr passiert ist — Ausfälle stehen in den Logs.
Über diesen Kanal gibt es **grundsätzlich** keine Run-to-failure-Historie (nicht
„noch nicht"). Eine supervised Ausfallvorhersage hat damit dauerhaft kein echtes
Trainingsmaterial; sie wird trotzdem **vollständig und methodisch korrekt** gebaut.

---

## 4. Features

Pro Datenpunkt (verschlüsselt über den stabilen `data_points.name`, der Training und
Inferenz konsistent verbindet) Aggregate aus dem Continuous Aggregate `readings_1m`
über das Vorlauf-Fenster: Mittel, Std, Min, Max, Range, RMS, Trend-Steigung
(Least-Squares), Rate-of-Change, Last-Wert, Last-minus-Mittel, Abdeckung. Dazu:

- **Drift-Output als Feature** (Kopplung der Reasoner): Anzahl / max. Effektstärke /
  Zeit-seit-letzter-Drift aus dem F4-Drift-Reasoner. Im Training aus
  `detect_drift_in_stream`, in der Inferenz aus den `drift_detected`-`semantic_events`
  (tragen `detected_at` + `effect_size`, zeitlich korrekt auch bei Backfill).
  **Gating-Annahme:** Der Trainingspfad fährt die Drift-Detektion bewusst *ungegatet*
  (`runs=[]`), die Inferenz gatet über die `production_runs` der Linie. Beide stimmen
  überein, solange die Ziel-Linie **keine `production_runs`** führt (so bei allen
  ausgelieferten Failure-Szenarien). Mit echten `production_runs` gatet die Inferenz
  enger → andere `drift__count`/`drift__hours_since_last`; beim Realdaten-Wechsel (§8)
  ist die Drift-Quelle/Gating-Annahme anzugleichen.
- **Wartung**: Zeit seit letzter Wartung (kumulativ).
- **Alarm-Historie**: Anzahl Nicht-Drift-Alarme im Fenster.

Das Artefakt fixiert ein **Feature-Schema** (126 Spalten — die Vereinigung der
Datenpunkt-Namen aller Trainingsszenarien). Führt eine Maschine einen Datenpunkt
nicht, wird das Feature zu `NaN` (LightGBM-konform). Features sind **PII-frei**:
Zahlen über technische Tags, keine Klartext-Identitäten, keine Werker-Freitexte.

Die Zahlen (Wahrscheinlichkeit, SHAP-Werte) sind **autoritativ vom Modell** — sie
kommen nie aus einem LLM (Grundlage für den späteren Erklär-Layer; Konsistenz mit dem
Gateway-Vertrag §13.3).

---

## 5. Modell & Training

- `LGBMClassifier` (binär), `scale_pos_weight` aus der Train-Klassenbalance,
  reproduzierbar über `--seed` (`deterministic=True`, einkernig).
- **Schwellwert** kostensensitiv auf der PR-Kurve gewählt: niedrigster Schwellwert mit
  Recall ≥ 0,80 bei maximaler Precision (nicht 0,5). Im Artefakt 0,997 — Folge der
  near-perfekten Eval-Trennschärfe auf Sim-Daten (§7).
- **Baseline**: Eine logistische Regression mit Class-Weights ist als Pflicht-Baseline
  vorgesehen; der prädiktive Feinschliff (Hyperparameter-Suche) lohnt erst mit
  Realdaten und ist bewusst **nicht** in Scope.

---

## 6. Metriken — Funktionsnachweis, nicht Realitätsnachweis

Eval auf dem **lauf-disjunkten** Split, klassenungleichgewicht-taugliche Metriken:

| Metrik | Wert (Artefakt) | Bedeutung |
|---|---|---|
| **PR-AUC** (Average Precision, primär) | **0,998** | Trennschärfe auf Sim-Eval |
| ROC-AUC | 0,998 | Rangordnung auf Sim-Eval |
| Brier | 0,025 | Kalibrierung auf Sim-Eval |

> **Diese Werte sind ein Funktionsnachweis (die Pipeline rechnet korrekt), kein
> Realitätsnachweis.** PR-AUC 0,998 heißt **nicht** „sagt 99,8 % der realen Ausfälle
> vorher" — es heißt „hat den Simulator nahezu vollständig zurückgelernt". Genau diese
> fast perfekten Zahlen sind der empirische Beleg für die Zirkularität aus §7.1:
> Features und Labels stammen vom selben Generator nach bekannten Regeln; das Modell
> rekonstruiert ihn, es entdeckt nichts.

So benannt in der Model Card, im Code-Header (`train.py`) und im Trainings-Log
(`train_summary` druckt das Banner bei jedem Lauf).

---

## 7. Warum Simulationsdaten für eine Ausfallvorhersage nicht genügen

*— und was echte Daten leisten müssten. Dies ist das Herzstück dieser Karte.*

### 7.1 Zirkularität / Generator-Rückgewinnung

Sind **Features und Labels vom selben Simulator** nach bekannten Regeln erzeugt, kann
das Modell bestenfalls genau diese Regeln zurücklernen. Es entdeckt nichts; es
**rekonstruiert den Generator**. Der Lagerschaden ist im Sim per Konstruktion eine
Vibrations-Ramp ab einem bekannten t\* — das Modell lernt „steigende
Vibrations-Steigung ⇒ Ausfall im Horizont", weil genau das hineinprogrammiert wurde.
Hohe Eval-Werte (hier PR-AUC 0,998) heißen **„Simulator gelernt"**, nicht „reale
Ausfälle vorhergesagt". Je realistischer der Simulator, desto überzeugender — und
desto trügerischer — die Zahl.

### 7.2 Reality Gap

Der Simulator bildet eine **vereinfachte, vorab antizipierte** Welt ab: die
Degradationspfade, die sein Autor kannte und einbaute. Reale Maschinen versagen über
**unmodellierte Kopplungen** (Vibration × Temperatur × Last × Material gleichzeitig),
**seltene Kombinationen** und **Materialermüdung mit nicht-modelliertem Verlauf** —
also genau über die **unvorhergesehenen Pfade**, die ein Vorhersagesystem fangen
soll. Diese fehlen im Sim-Material **per Konstruktion**: Was niemand antizipiert hat,
kann der Generator nicht erzeugen, und das Modell kann es nicht lernen.

### 7.3 Label-Authentizität

Reale Ausfall-Labels sind **unscharf und verrauscht**: Wann „begann" der Ausfall —
beim ersten Mikroriss, beim hörbaren Geräusch, beim Stillstand? Es gibt
Fehldiagnosen, nachgetragene oder fehlende Einträge, „repariert, aber eigentlich war's
was anderes". Sim-Labels sind **perfekt und deterministisch** (der Offset steht in
`ground_truth.failure`). Das Modell lernt eine **Trennschärfe, die real nie
existiert**, und überschätzt damit systematisch seine eigene Sicherheit — auch das
schlägt sich in den near-perfekten Eval-Zahlen nieder.

### 7.4 Basisrate & Heterogenität

Reale Ausfälle sind **selten und vielgestaltig**; ihre **Basisrate**, ihre
**Modus-Vielfalt** (Lager, Werkzeug, Schmierung, Elektrik, Steuerung …) und die
**Streuung ihres Vorlaufs** lassen sich nicht glaubwürdig synthetisieren. Der
Simulator setzt eine **künstliche Rate** (hier: rund 60 % positive Trainings-Fenster)
— die reale Schwierigkeit ist die **Nadel im Heuhaufen** (Ausfälle als seltenes
Ereignis), und genau diese Schwierigkeit ist im Sim-Material wegdefiniert.

### 7.5 Feature-Realismus

Reales **Sensorrauschen, Kalibrierungsdrift und Betriebspunkt-Wechsel** verschieben
die Feature-Verteilung gegenüber dem Sim. Was im Simulator ein **klares Signal** ist
(eine saubere Ramp über dem Grundrauschen), liegt real oft **im Rauschen** oder unter
einem Schichtwechsel-Sprung verborgen. Ein auf sauberen Sim-Verteilungen trainiertes
Modell trifft real auf eine andere Verteilung (Covariate Shift) und ist dort nicht
mehr kalibriert.

### 7.6 Verifikation ≠ Validierung — die ehrliche Kernaussage

Die Pipeline lässt sich technisch **verifizieren**: Funktioniert sie korrekt? Kein
Zeit-Leakage? Reproduzierbar? Schema erzwungen? — Ja, und das ist hier umfassend
getestet. Ohne reale Ground Truth lässt sie sich aber nicht **validieren**: Sagt sie
die Realität richtig vorher? — Das ist **unbeantwortbar** auf Sim-Daten.

> **Verifikation ist eine Aussage über den Code. Validierung ist eine Aussage über die
> Welt.** Dieses Modul ist verifiziert, nicht validiert. Diese Unterscheidung ist die
> ehrliche Kernaussage des Moduls — und der Grund, warum `validation_status` ein
> Pflichtfeld ist.

---

## 8. Was echte Daten leisten + Migrationspfad

Nur eine **reale Run-to-failure-Historie** enthält die **unvorhergesehenen Pfade**
(§7.2), die **echten Label-Unschärfen** (§7.3), die **echte Basisrate und
Modus-Vielfalt** (§7.4) und die **reale Feature-Verteilung** (§7.5) — und **erst gegen
sie** ist das Modell validierbar (§7.6). Synthetik darf **trainieren**, die **Abnahme**
läuft ausschließlich auf echten Ausfällen.

Die Pipeline ist so gebaut, dass der Wechsel **trivial** ist:

- **gleiche Feature-Definition** (`features.py`, rein/netzfrei, über `data_points.name`
  verschlüsselt — funktioniert auf Sim- wie Realdaten identisch). **Beim Wechsel
  anzugleichen** (heute durch die Sim-Erzeugung garantiert, dann nicht mehr): dieselbe
  Drift-Gating-Annahme (§4), Quality-/Missing-Behandlung und minutenausgerichtete
  Bucket-Bildung (`readings_1m`) wie die Inferenz — der Datensatzbau erzwingt diese
  Invarianten heute per Fail-fast,
- **gleiche Trainings-CLI** (`train.py`), **gleiches Artefakt-Format**,
- **nur ein reales, gelabeltes Trainingsset** ersetzt die Szenario-Generierung in
  `dataset.py` (bzw. lädt reale Fenster statt sie zu simulieren).

Beim Wechsel wird `training_source`/`data_regime`/`validation_status` auf das reale
Regime gehoben — **aus dem Demonstrator wird ein validierbarer Prädiktor**. Solange
das nicht passiert ist, bleibt der Vorbehalt strukturell erzwungen.

**Zwischenschritt (ehrlich).** Bei sehr wenigen echten Ausfällen ist der seriöse
Output ein **kalibriertes Risiko-Ranking** („diese Komponenten zuerst prüfen") statt
einer scheingenauen Wahrscheinlichkeit; Unsicherheit (`data_caveats`) gehört in den
Output. Schwache Labels (Reparatur/Austausch aus `maintenance_events`, kritische
`alarms`) sind ein Ausfall-**Proxy** mit dokumentiertem Label-Rauschen.

---

## 9. Strukturelle Verankerung der Ehrlichkeit

Der Vorbehalt ist nicht abstreifbar, weil er an drei Stellen **erzwungen** ist:

1. **Datenobjekt.** `FailurePrediction` (Pydantic, `extra=forbid`) trägt
   `validation_status` als **Pflichtfeld ohne Default** mit dem einzigen erlaubten
   Wert `simulation_only`; dazu `data_regime` und `model_version` aus den
   Artefakt-Metadaten. Es gibt **keinen Konstruktionsweg** ohne den Vorbehalt — jeder
   Konsument (Persistenz, Dashboard, MCP, späterer Erklär-Layer) muss ihn mitführen.
   *Getestet:* eine Vorhersage ohne `validation_status` ist nicht konstruierbar; die
   E2E-Pipeline trägt ihn immer.
2. **Metrik.** Alle `foreman_failure_*`-Kennzahlen tragen das Label
   `data_regime="simulation"` — der Sim-Vorbehalt ist auch im Monitoring sichtbar.
3. **Persistenz.** Die Tabelle `failure_predictions` führt `validation_status`,
   `data_regime` und `model_version` als Spalten — der Vorbehalt überlebt die
   Speicherung.

---

## 10. Limitationen (Kurzfassung)

- **Nicht validiert** (§6/§7). Eval-Werte = Funktionsnachweis.
- **Generator-Rückgewinnung** statt Entdeckung (§7.1).
- **Reality Gap, Label-/Basisraten-/Feature-Artefakte** der Simulation (§7.2–§7.5).
- **SHAP ist assoziativ, nicht kausal**: Ein Top-Faktor „erhöht das Risikomodell-Signal",
  er „verursacht" den Ausfall nicht. Der spätere LLM-Erklär-Layer darf das nicht
  umdeuten; er erfindet keine Werte.
- Kein Laufzeit-Training; on-demand, keine Aktorik.

---

## 11. Referenzen

- Methodenwahl & Quellen-Fundament: `docs/research/ausfallvorhersage-methodenwahl.md`
  (LightGBM, SHAP TreeExplainer, PR-AUC, Class-Weights vs. SMOTE, zeit-/gruppenbewusste
  Splits, C-MAPSS u. a.).
- Drift-Kopplung (Drift-Output als Feature): `docs/research/drift-erkennung-verfahren.md`.
- Plattform-Vertrag: `GROUND_TRUTH.md` §16 (Ausfallvorhersage), §5 (`failure_predictions`,
  Migration `0005`), §12.5 (`ground_truth.failure`), §11.2 (`foreman_failure_*`).
