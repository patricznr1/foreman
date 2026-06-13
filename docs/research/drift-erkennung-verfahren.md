# Auswahl eines Drift-Erkennungs-Verfahrens für den FOREMAN-Drift-Reasoner

> Technisches Research-Dokument · Stand Juni 2026
> Scope: Wahl des Algorithmus und der Library für den **Drift-Reasoner** — den ersten Reasoner der FOREMAN-Plattform (Sprint F4). Dieser erkennt Verhaltensänderungen einer Maschine **gegen ihr eigenes historisches Profil**, nicht gegen statische Schwellwerte.
> Datengrundlage: Maschinen-Sensorik (Vibration, Temperatur, Drehmoment, Spindeldrehzahl, Energieverbrauch) als Zeitreihen in PostgreSQL/TimescaleDB (`readings(time, data_point_id, value, quality)`).
>
> **IP-Hinweis:** Verfahren wie ADWIN werden hier ausschließlich als allgemein bekannte, publizierte Methoden diskutiert und für den **FOREMAN-eigenen Reasoner-Code** bewertet. Über die interne Arbeitsweise des externen Gedächtnis-Substrats (Black Box hinter HTTP-API) wird **keine** Aussage getroffen. Was der Substrat-Dienst intern tut, ist für dieses Dokument irrelevant; bewertet wird, was FOREMAN selbst implementiert.

---

## 1. Fragestellung

Klassische Industrie-Observability alarmiert gegen feste Grenzwerte (`normal_min`/`normal_max` pro `data_point`). Das übersieht den wichtigsten Fall: eine Maschine, deren Verhalten sich *innerhalb* der erlaubten Grenzen schleichend verschiebt — ein Lager, dessen Vibrationssignatur über Wochen wandert; eine Spindel, deren Energieaufnahme bei gleicher Last langsam steigt. Genau diese **Verteilungs- bzw. Verhaltensänderung gegen das eigene historische Profil** ist „Concept Drift" im technischen Sinn, und ihre frühe Erkennung ist der Kern des Drift-Reasoners.

Das Dokument beantwortet sechs Forschungsfragen:

1. Überblick und Klassifikation der Verfahren (ADWIN, Page-Hinkley, KSWIN, DDM/EDDM, CUSUM, KS-Test, Wasserstein).
2. Eignung für industrielle Sensordaten (Saisonalität durch Schichtbetrieb, Rüstvorgänge, geplante Stillstände, Rauschen, fehlende Werte) und wo Fehlalarme entstehen.
3. Abgrenzung Drift-Erkennung vs. Anomalie-Erkennung vs. Ausfallvorhersage.
4. Parametrisierung und Kalibrierung ohne große gelabelte Ausfall-Datensätze.
5. Python-Implementierungsoptionen (river, scikit-multiflow, alibi-detect, Frouros, Eigenbau) — Reife, Wartung, Lizenz, async-FastAPI-Tauglichkeit.
6. Validierung ohne Ground Truth.

Der Abschluss (Abschnitt 6 und 7) benennt eine eindeutige, baubare Wahl mit konkreten Parameterwerten und Code. Tradeoffs stehen im Vergleichsteil davor (Abschnitt 5), nicht im Schluss.

---

## 2. Verfahrensüberblick und Klassifikation

Begrifflich sind zwei Familien zu trennen, die in der Praxis verschwimmen:

- **Change-Point-/Sequenzielle-Detektion** auf einem eindimensionalen Signalstrom: CUSUM, Page-Hinkley, ADWIN. Frage: „Hat sich Mittelwert/Niveau des Stroms signifikant verschoben?"
- **Zwei-Stichproben-Verteilungstests** zwischen einem Referenz- und einem aktuellen Fenster: Kolmogorow-Smirnow (KS), Cramér-von-Mises, Wasserstein-Distanz, Maximum Mean Discrepancy (MMD). Frage: „Unterscheidet sich die Verteilung *jetzt* von der Verteilung *früher*?"

Eine dritte, ursprünglich für überwachtes Lernen gedachte Familie überwacht die **Fehlerrate eines Vorhersagemodells**: DDM, EDDM. Sie braucht ein Label-Signal (richtig/falsch) und ist für reine, unlabeled Sensorströme nur indirekt nutzbar.

### 2.1 ADWIN (ADaptive WINdowing)

*Bifet & Gavaldà, „Learning from Time-Changing Data with Adaptive Windowing", SDM 2007.* Hält ein gleitendes Fenster variabler Länge. Wann immer zwei hinreichend große Teilfenster (älterer vs. jüngerer Abschnitt) **statistisch unterschiedliche Mittelwerte** zeigen (Hoeffding-Schranke), wird der alte Teil verworfen und Drift gemeldet. Das Fenster **wächst** bei Stationarität (mehr Genauigkeit) und **schrumpft** bei Änderung (schnelle Reaktion). Die effiziente Variante ADWIN2 nutzt eine exponentielle Histogramm-Struktur (O(log W) Speicher).

- *Annahmen:* eindimensionaler Strom beschränkter Realwerte; Drift = Mittelwertverschiebung.
- *Stärken:* **kein Fenster zu raten** (selbst-adaptiv), formale Schranken für False-Positive/False-Negative-Raten, ein einziger intuitiver Parameter (`delta`), sehr geringer Speicher, echtes Online-Verfahren.
- *Schwächen:* erkennt primär Verschiebungen in Lage/Mittelwert; reine Varianz-/Formänderung ohne Mittelwertshift wird schwächer erfasst; auf rohen saisonalen Signalen schlägt es bei jedem Schichtwechsel an.

### 2.2 Page-Hinkley (PH)

*Page, „Continuous Inspection Schemes", Biometrika 1954* — eine Variante des CUSUM-Tests. Akkumuliert die vorzeichenbehaftete Abweichung der Beobachtungen vom laufenden Mittel und meldet Drift, wenn die kumulierte Abweichung eine Schranke `λ` überschreitet; ein Toleranzparameter `δ` ignoriert kleines Rauschen.

- *Annahmen:* Mittelwert eines (annähernd gaußschen) Signals springt oder driftet monoton.
- *Stärken:* extrem leichtgewichtig (O(1) Speicher/Update), sehr gut für **monotone Trends** (Lagerverschleiß, langsam steigende Temperatur).
- *Schwächen:* zwei manuell zu kalibrierende Parameter (`λ`, `δ`); empfindlich gegen die Wahl; reagiert auf Saisonalität ebenfalls mit Fehlalarmen.

### 2.3 CUSUM

Der klassische kumulative-Summen-Test (Page 1954), Vorläufer von PH. Gleiche Grundidee (kumulierte Abweichung gegen Schwelle), in der Praxis für Sensordrift meist als Page-Hinkley-Form implementiert. Sehr etabliert in der statistischen Prozesskontrolle (SPC), aber annahmebehaftet (bekannte/stabile Referenzparameter) und parametersensibel.

### 2.4 KSWIN (Kolmogorov-Smirnov WINdowing)

*Raab, Heusinger & Schleif, „Reactive Soft Prototype Computing for Concept Drift Streams", Neurocomputing 416 (2020), 340–351.* Hält ein Fenster der letzten `n` Werte; vergleicht die `r` jüngsten gegen `n−r` ältere (zufällig gezogene) per **Kolmogorow-Smirnow-Zwei-Stichproben-Test**. Drift, wenn der KS-Abstand signifikant ist (`α`).

- *Annahmen:* **keine** Verteilungsannahme (nicht-parametrisch) — fängt auch Form-/Varianzänderungen, nicht nur Mittelwertshifts.
- *Stärken:* sensibel für vielfältige Verteilungsänderungen; gut dokumentiert; in mehreren Libraries vorhanden.
- *Schwächen:* drei Parameter (`alpha`, `window_size`, `stat_size`); empfindlich gegen `α` (zu hoch → Fehlalarme); fixe Fenstergröße muss zur Drift-Geschwindigkeit passen.

### 2.5 DDM / EDDM

*Gama et al., „Learning with Drift Detection", SBIA 2004 (DDM); Baena-García et al., 2006 (EDDM).* Überwachen die **Fehlerrate eines Klassifikators** über den Strom: steigt sie signifikant (DDM) bzw. ändert sich der Abstand zwischen Fehlern (EDDM, gut für graduelle Drift), wird Warnung/Drift gemeldet.

- *Annahmen:* es existiert ein **überwachtes Fehler-Signal** (Label).
- *Eignung FOREMAN:* nur indirekt — erst sinnvoll, wenn ein Vorhersagemodell (Ausfallvorhersage-Reasoner) läuft und man dessen Fehler-Drift überwachen will. Für die reine, label-arme Sensorüberwachung des Drift-Reasoners **nicht** der primäre Pfad.

### 2.6 Verteilungstests: KS, Wasserstein, MMD

Zwei-Stichproben-Tests zwischen Referenz- und Aktuell-Fenster. **KS** misst die maximale Differenz der empirischen Verteilungsfunktionen; **Wasserstein** (Earth Mover's Distance) misst den „Transportaufwand" zwischen zwei Verteilungen und ist sensibel auch für Verschiebungen der gesamten Verteilung; **MMD** ist ein Kernel-basiertes, mehrdimensionales Maß. Sie sind die Basis der Batch-/Offline-Drift-Detektoren (z. B. in alibi-detect) und eignen sich für periodische Vergleiche „aktuelle Woche vs. Referenzprofil" — weniger für das streaming-nahe, sample-für-sample Monitoring.

---

## 3. Eignungsanalyse für industrielle Zeitreihen

Der entscheidende Punkt: **Kein Detektor ist gegen Saisonalität immun, wenn man ihn auf das Rohsignal wirft.** Industrielle Sensordaten sind hochgradig nicht-stationär *aus betrieblichen, nicht aus Verschleiß-Gründen*. Genau diese betrieblichen Muster erzeugen die Fehlalarme:

- **Schichtbetrieb / Saisonalität:** Last- und damit Temperatur-/Energie-/Drehmomentprofile unterscheiden sich systematisch zwischen Früh-, Spät-, Nachtschicht und Wochenende. Ein roher ADWIN/PH/KSWIN meldet bei jedem Schicht- oder Produktwechsel „Drift" — korrekt im statistischen, falsch im betrieblichen Sinn.
- **Rüstvorgänge / Produktwechsel:** Andere Werkstücke → anderer Arbeitspunkt. Ohne Kontext sieht der Detektor einen abrupten Concept-Shift.
- **Geplante Stillstände:** Energie/Drehzahl fallen auf null. Ein Detektor auf dem Rohsignal interpretiert Anlauf/Auslauf als massive Drift.
- **Sensor-Rauschen:** hochfrequentes Rauschen bläht Fenster auf und triggert verteilungsbasierte Tests; reine Schwellen-Akkumulatoren (PH) reagieren auf Ausreißer.
- **Fehlende Werte / Quality-Flags:** Lücken (`quality`-Flag, NULL) dürfen nicht als Wert „0" interpretiert werden.

**Konsequenz — die Architektur entscheidet mehr als der Algorithmus.** Der Detektor darf nicht auf dem Rohsignal laufen, sondern auf einem **kontext-bereinigten, abgeleiteten Strom**. Drei Bausteine, die *vor* den Detektor gehören:

1. **State-Gating:** Nur Samples einfließen lassen, in denen die Maschine in einem **vergleichbaren Betriebszustand** ist (laufender `production_run`, kein Rüsten, kein Stillstand). Zustand kommt aus `production_runs` und digitalen `data_points` (kind=digital). Außerhalb → Detektor pausieren, nicht füttern.
2. **Deseasonalisierung / Normierung:** Statt des Rohwerts ein **Residuum gegen ein erwartetes Profil** je Betriebszustand füttern (z. B. Wert minus gleitender Median des gleichen Zustands, oder z-Score gegen das zustandsspezifische Mittel). Damit verschwindet die betriebliche Saisonalität, und übrig bleibt die *verschleißbedingte* Abweichung — genau das Zielsignal.
3. **Downsampling/Glättung:** Drift ist langsam (Stunden bis Wochen). Hochfrequente Rohwerte (z. B. 10 Hz) auf ein robustes Aggregat pro Intervall reduzieren (Median/Mittel pro Minute), Rauschen dämpfen, Rechenlast senken. Fehlende Intervalle überspringen, nicht interpolieren-als-Wert.

Auf diesem bereinigten Residuumstrom ist **ADWIN** besonders attraktiv: Es braucht keine geratene Fenstergröße (die bei wechselnden Drift-Geschwindigkeiten ohnehin falsch wäre), reagiert schnell bei echter Änderung und ist durch `delta` konservativ einstellbar. KSWIN bliebe als Ergänzung für reine Form-/Varianzänderungen sinnvoll, bringt aber drei Parameter und eine fixe Fenstergröße mit.

---

## 4. Abgrenzung: Drift vs. Anomalie vs. Ausfallvorhersage

Diese drei werden im Industrie-Sprachgebrauch vermischt, gehören in FOREMAN aber in **getrennte Reasoner** mit verschiedenen Methoden, Zeithorizonten und Datenanforderungen.

| Aufgabe | Frage | Zeithorizont | Methodik | Label-Bedarf | FOREMAN-Reasoner |
|---|---|---|---|---|---|
| **Anomalie-Erkennung** | „Ist *dieser Messwert/dieses kurze Fenster* abnormal?" | jetzt / Sekunden | Schwellwert, Isolation Forest, Autoencoder, kontextueller Ausreißer | keiner (unsupervised) | nicht dieser Reasoner; teils über `alarms` / späterer Anomalie-Pfad |
| **Drift-Erkennung** | „Hat sich das **Normalverhalten** dieser Maschine gegen ihr eigenes Profil verschoben?" | Stunden–Wochen | Change-Detection auf Residuumstrom (ADWIN/PH/KSWIN) | keiner | **Drift-Reasoner (F4, dieses Dokument)** |
| **Ausfallvorhersage** | „**Wann/Mit welcher Wahrscheinlichkeit** fällt die Maschine aus (RUL)?" | Tage–Monate | Regression/Survival (XGBoost), supervised | Ausfall-Labels nötig | Ausfallvorhersage-Reasoner (späterer Sprint) |

Die Grenzen in Worten: Anomalie ist **punktuell und sofort** (ein Spike), Drift ist **graduell und relativ zum eigenen Verlauf** (der Spike-freie, aber wandernde Mittelwert), Ausfallvorhersage ist **prognostisch und braucht historische Ausfälle als Wahrheit**. Der Drift-Reasoner ist bewusst der erste, weil er **kein gelabeltes Ausfallwissen voraussetzt** — er definiert „normal" aus der Maschine selbst. Sein Output ist ein **Frühwarnsignal** („Verhalten von Maschine X an Komponente Y hat sich verschoben"), das später als Feature in die Ausfallvorhersage eingeht. Er trifft keine Ausfall-Aussage und ersetzt keine Anomalie-Schwelle für akute Ereignisse (die bleiben bei `alarms`, Human-in-the-Loop).

---

## 5. Implementierungsoptionen im Vergleich

### 5.1 Verfahrens-Vergleich

| Verfahren | Erkannter Drift-Typ | Rechenaufwand | Parametrisierungs-Aufwand | Robustheit ggü. Saisonalität* | Library-Support |
|---|---|---|---|---|---|
| **ADWIN** | abrupt + graduell (Mittelwert/Lage) | sehr gering (O(log W)) | **minimal** (1 Param `delta`, selbst-adaptives Fenster) | gering auf Rohsignal / **gut auf Residuum** | river, Frouros, (skmultiflow) |
| **Page-Hinkley** | monotone Trends, Sprünge | minimal (O(1)) | mittel (`λ`, `δ`, `α`) | gering / gut auf Residuum | river, Frouros, (skmultiflow) |
| **CUSUM** | Mittelwertsprung | minimal (O(1)) | mittel-hoch (Referenzparameter) | gering | teils (SPC-Code, Eigenbau) |
| **KSWIN** | verteilungsweit (Form/Varianz) | mittel (KS auf Fenster) | mittel-hoch (`alpha`, `window`, `stat_size`) | gering / mittel auf Residuum | river, Frouros, (skmultiflow) |
| **DDM / EDDM** | Fehlerraten-Drift (supervised) | gering | mittel | n/a (braucht Labels) | river, Frouros, (skmultiflow) |
| **KS / Wasserstein / MMD (Batch)** | verteilungsweit, mehrdim. | hoch (Fenstervergleich) | mittel | mittel (periodischer Referenzvergleich) | alibi-detect, scipy, Frouros |

\* „auf Residuum" = nach State-Gating + Deseasonalisierung (Abschnitt 3). Kein Verfahren ist auf dem **Rohsignal** saisonrobust.

### 5.2 Library-Vergleich (Stand 2026)

| Library | Version (≈ 2026) | Lizenz | Wartung | Drift-Detektoren | async-FastAPI-Eignung |
|---|---|---|---|---|---|
| **river** | 0.22.x | **BSD-3 (permissiv)** | aktiv, De-facto-Standard für Streaming-ML | ADWIN, Page-Hinkley, KSWIN, DDM, EDDM, HDDM u. a. | **sehr gut** — reines Python, winzige Detektor-Objekte, inkrementell, kein TF/PyTorch, kein Blocking |
| **scikit-multiflow** | 0.5.3 (eingefroren) | BSD-3 | **nur Minimal-Pflege**, in river aufgegangen | ADWIN, DDM, EDDM, KSWIN, PH | nicht empfohlen (Nachfolger ist river) |
| **alibi-detect** | 0.13.0 | **BSL 1.1 (nicht-OSS, Produktion kostenpflichtig)** | aktiv (Seldon) | KSDrift, MMDDrift, CVMDrift, ChiSquare, TabularDrift u. a. | mittel — TF/PyTorch-Backends, schwergewichtig; **Lizenz blockiert** kommerziellen/air-gap-Einsatz |
| **Frouros** | 0.x | BSD-3 (permissiv) | aktiv, dediziert für Drift | ADWIN, PH, KSWIN, DDM, CUSUM, Verteilungstests | gut — leichtgewichtig, aber kleineres Ökosystem als river |

**Lesart.** `alibi-detect` ist technisch stark (mehrdimensionale MMD/KS-Detektoren), fällt aber für FOREMAN an der **Lizenz** aus: Die Business Source License 1.1 erlaubt produktiven Einsatz nur gegen kommerzielle Lizenz — unvereinbar mit FOREMANs permissivem, air-gap-fähigem Stack (Apache/BSD) und dem Freelance-/Produkt-Pfad. `scikit-multiflow` ist eingefroren (creme + scikit-multiflow → river). `Frouros` ist eine saubere, permissive Alternative, aber river hat das größere Ökosystem, die bessere Dokumentation und denselben Algorithmus bei mehr Reichweite. **river ist die naheliegende Wahl**: permissiv lizenziert, aktiv gepflegt, leichtgewichtig genug für einen async-FastAPI-Service, mit ADWIN, Page-Hinkley und KSWIN allesamt an Bord.

Eigenbau (ADWIN/PH selbst implementieren) ist nicht nötig und wäre Risiko: ADWIN korrekt mit Hoeffding-Schranken und exponentiellem Histogramm zu bauen ist fehleranfällig; river liefert die geprüfte Referenzimplementierung.

---

## 6. Empfehlung für FOREMAN

**Verfahren: ADWIN als primärer Drift-Detektor**, betrieben **pro `data_point`** auf einem **state-gated, deseasonalisierten Residuumstrom**. Optionaler Zweitdetektor **KSWIN** je `data_point` für reine Form-/Varianzänderungen, sobald der ADWIN-Pfad steht (nicht im ersten Wurf).

**Library: `river` (≥ 0.21, Ziel 0.22.x), Lizenz BSD-3.** Permissiv, aktiv gepflegt, leichtgewichtig, async-FastAPI-tauglich. Kein alibi-detect (BSL), kein scikit-multiflow (eingefroren).

**Begründung in einem Satz:** ADWIN braucht keine geratene Fenstergröße, reagiert schnell auf echte Verhaltensänderung, hat einen einzigen verständlichen Parameter und kostet quasi nichts an Rechenleistung — und river stellt es unter einer Lizenz bereit, die FOREMANs kommerziellen und air-gap-Pfad nicht verbaut. Die Saisonalität wird nicht vom Algorithmus, sondern von der vorgelagerten Residuumbildung erschlagen.

### 6.1 Konkrete Parameterwerte (Startkalibrierung)

| Parameter | Startwert | Begründung / Tuning |
|---|---|---|
| ADWIN `delta` | **0.002** | river-Default. Kleineres `delta` (→ 0.001) = konservativer, weniger Fehlalarme, etwas längere Latenz. Bei zu vielen Fehlalarmen senken. |
| Warm-up (Mindest-Samples je `data_point`) | **≥ 100** Residuum-Samples | Vor Erreichen kein Drift-Signal vertrauen (Profil noch nicht etabliert). |
| Grace-Period nach Zustandswechsel | **5 min** (bzw. ein paar Samples) | Nach Rüsten/Anlauf Detektor pausieren, bis stationärer Betrieb wieder erreicht ist. |
| Aggregations-Intervall (Downsampling) | **1 Sample / Minute** (Median) | Drift ist langsam; dämpft Rauschen, senkt Last. Bei sehr trägen Größen (Temperatur) auch gröber. |
| Residuum-Baseline | **gleitender Median je Betriebszustand**, Fenster z. B. 24 h | Entfernt Schicht-/Produkt-Saisonalität; übrig bleibt Verschleißsignal. |
| KSWIN (optional) `alpha` / `window_size` / `stat_size` | 0.005 / 200 / 50 | Erst nach ADWIN-Pfad; `alpha` bewusst niedrig gegen Fehlalarme. |

Diese Werte sind eine **begründete Startkalibrierung**, kein Endzustand — Abschnitt 7 beschreibt, wie sie ohne Ausfall-Labels validiert und nachgezogen werden.

### 6.2 Kopierbares Code-Snippet (async-FastAPI-Service)

```python
# foreman/reasoners/drift/detector.py
"""Drift-Reasoner: ADWIN je data_point auf einem state-gated, deseasonalisierten
Residuumstrom. Library: river (BSD-3). Substrat bleibt aussen vor — dieser Code
rechnet ausschliesslich auf FOREMANs eigenen readings."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field

from river import drift  # river >= 0.21 (Ziel 0.22.x)

WARMUP_MIN_SAMPLES = 100          # vor diesem Stand kein Drift-Signal vertrauen
BASELINE_WINDOW = 1440            # gleitende Baseline: 1440 Min = 24 h bei 1/min


@dataclass
class DataPointDriftState:
    """Detektor-Zustand fuer EINEN data_point. Bewusst winzig -> tausende parallel ok."""
    adwin: drift.ADWIN = field(default_factory=lambda: drift.ADWIN(delta=0.002))
    baseline: deque[float] = field(default_factory=lambda: deque(maxlen=BASELINE_WINDOW))
    seen: int = 0

    def _residual(self, value: float) -> float:
        # Deseasonalisierung: Wert minus gleitender Median des aktuellen Zustands.
        if not self.baseline:
            return 0.0
        s = sorted(self.baseline)
        median = s[len(s) // 2]
        return value - median

    def update(self, value: float, *, in_steady_state: bool) -> bool:
        """Einen (aggregierten) Messwert verarbeiten. Gibt True NUR bei echter Drift.

        in_steady_state: aus production_runs + digitalen data_points abgeleitet.
        Faellt es weg (Ruesten/Stillstand/Anlauf), wird NICHT gefuettert -> kein Fehlalarm.
        """
        if not in_steady_state:
            return False
        residual = self._residual(value)
        self.baseline.append(value)
        self.seen += 1
        self.adwin.update(residual)
        if self.seen < WARMUP_MIN_SAMPLES:
            return False
        return bool(self.adwin.drift_detected)


class DriftReasoner:
    """Haelt je data_point einen Detektor. Stateful, in-memory, prozesslokal."""
    def __init__(self) -> None:
        self._states: dict[int, DataPointDriftState] = {}

    def observe(self, data_point_id: int, value: float, *, in_steady_state: bool) -> bool:
        st = self._states.setdefault(data_point_id, DataPointDriftState())
        return st.update(value, in_steady_state=in_steady_state)
```

```python
# foreman/reasoners/drift/router.py
"""Async-FastAPI-Einbindung. CPU-leichte, nicht-blockierende Detektor-Updates
laufen direkt im Event-Loop; nur DB-I/O ist awaited."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from foreman.reasoners.drift.detector import DriftReasoner

router = APIRouter(prefix="/api/v1/reasoners/drift", tags=["drift"])

# Ein prozessweiter Reasoner-Zustand (pro Worker). Bei mehreren Workern:
# Detektor-Zustand pro data_point an einen Worker pinnen ODER periodisch
# aus readings rehydrieren (siehe offene Punkte).
_reasoner = DriftReasoner()


class ReadingIn(BaseModel):
    data_point_id: int
    value: float
    in_steady_state: bool = True


class DriftOut(BaseModel):
    data_point_id: int
    drift_detected: bool


@router.post("/observe", response_model=DriftOut)
async def observe_reading(reading: ReadingIn) -> DriftOut:
    detected = _reasoner.observe(
        reading.data_point_id, reading.value, in_steady_state=reading.in_steady_state,
    )
    if detected:
        # Hier: Drift-Ereignis persistieren (z.B. als semantic_event / alarm,
        # Human-in-the-Loop). Bewusst NICHT aktorisch — FOREMAN empfiehlt nur.
        ...  # await persist_drift_event(reading.data_point_id)
    return DriftOut(data_point_id=reading.data_point_id, drift_detected=detected)
```

Hinweise: ADWIN-Updates sind CPU-billig und blockieren den Event-Loop nicht; ausschließlich Datenbank-/Substrat-I/O wird `await`-et. Der Detektor-Zustand ist klein genug, um tausende `data_points` im Speicher zu halten. Beim Batch-Ingest (`POST /api/v1/readings`, F3-Adapter) wird `observe()` pro aggregiertem Sample aufgerufen, nicht pro Rohwert.

---

## 7. Validierungsstrategie ohne Ground Truth

Echte Ausfalldaten sind knapp — das ist der Normalfall in der Industrie, kein FOREMAN-Sonderproblem. Die Qualität der Drift-Erkennung wird daher über **kontrollierte Drift** statt über echte Ausfälle nachgewiesen. Drei Ebenen:

1. **Synthetische Drift-Injektion (Hauptmethode).** Auf einen real aufgezeichneten, *stationären* Sensorabschnitt wird zu einem **bekannten Zeitpunkt t\*** eine definierte Drift aufmoduliert: Mittelwert-Sprung (abrupt), linearer Ramp (graduell, Verschleiß-Analogon), Varianz-Erhöhung. Gemessen wird gegen die so konstruierte Wahrheit:
   - **Detektionsverzug** (Samples/Minuten zwischen t\* und Meldung),
   - **Fehlalarmrate** auf den stationären Segmenten *vor* t\* (False Positives je Zeiteinheit),
   - **Trefferquote** (wird die injizierte Drift überhaupt erkannt) und **mittlere Zeit bis Fehlalarm** (MTFA) auf garantiert driftfreien Strecken.
   river bringt synthetische Drift-Stream-Generatoren mit, die sich für die abrupt/graduell-Fälle nutzen lassen; für sensor-realistische Tests wird die Injektion auf echten Abschnitten bevorzugt.

2. **Digitaler Zwilling aus SPS-Programmen.** Die aus den SPS-Programmen abgeleitete Simulation (ohnehin Teil des FOREMAN-Datenpfads, F3) wird mit **steuerbaren Degradations-Szenarien** gefahren — z. B. modelliertem Lagerverschleiß mit einstellbarer Rate. Hier ist die Drift **per Konstruktion** Ground Truth, inklusive eingebauter Schicht-Saisonalität und Rüstvorgänge, um die Fehlalarm-Robustheit des State-Gating real zu prüfen.

3. **Stationaritäts- und Saison-Sanity-Checks.** Auf bekannten **driftfreien** Betriebsphasen (gesunde Maschine, mehrere Schichten) darf der Detektor *nicht* feuern. Dieser Test deckt genau den gefährlichsten Fehlerfall ab: Saisonalität, die als Drift fehlinterpretiert wird. Er ist die Abnahmebedingung für die Residuumbildung aus Abschnitt 3.

Zielgrößen für die Abnahme (Startwerte, an Realdaten zu schärfen): Fehlalarmrate auf driftfreien Schicht-/Wochenenddaten ≈ 0 pro Woche und Maschine; injizierte graduelle Drift wird innerhalb eines betrieblich nützlichen Vorlaufs (Tage, nicht erst beim Ausfall) erkannt. Diese Metriken gehören in die Test-Suite (F4) und in die Observability (`/metrics`) — Detektionsverzug und Fehlalarmrate als laufende Kennzahlen.

---

## 8. Offene Punkte

- **Detektor-Zustand bei mehreren Workern:** In-Memory-Zustand pro Prozess kollidiert mit horizontaler Skalierung. Optionen: `data_point` → Worker pinnen; Zustand periodisch persistieren; oder bei Worker-Start aus `readings` rehydrieren (ADWIN-Fenster neu aufbauen). Für den MVP (ein Worker) unkritisch, vor Skalierung zu klären.
- **Residuum-Baseline pro Betriebszustand:** Der gleitende Median je Zustand ist die einfachste Deseasonalisierung. Ob Zustände fein genug aus `production_runs` + digitalen `data_points` ableitbar sind, ist an realen SPS-Daten zu prüfen; ggf. zustandsspezifische Baselines (Früh/Spät/Nacht × Produkt) statt eines globalen Medians.
- **Multivariate Drift:** Vorgeschlagen ist eine Detektor-Instanz **pro `data_point`** (univariat). Echte Lagerschäden zeigen sich oft erst in der **Korrelation** mehrerer Größen (Vibration × Temperatur × Drehmoment). Multivariate Verfahren (MMD, korrelationsbasiert) sind ein späterer Ausbau, nicht der erste Wurf.
- **Schwellwert für „nützliche" Drift:** ADWIN meldet *statistische* Signifikanz; betrieblich relevant ist erst eine Drift ab gewisser Größe/Dauer. Eine nachgelagerte Relevanz-Heuristik (Mindest-Effektgröße, Persistenz über N Intervalle) gegen Alarmmüdigkeit ist sinnvoll.
- **KSWIN-Zweitpfad:** Ob der Form-/Varianz-Detektor messbaren Mehrwert über ADWIN liefert, an den Validierungsdaten entscheiden, bevor er gebaut wird.
- **Substrat-Kopplung:** Ob und wie Drift-Ereignisse zusätzlich an den externen Gedächtnis-Dienst gemeldet werden, ist eine reine Integrationsfrage (HTTP) und für die hier getroffene Algorithmus-/Library-Wahl ohne Belang.

---

## Quellen

- A. Bifet, R. Gavaldà, *Learning from Time-Changing Data with Adaptive Windowing*, SIAM SDM 2007 (ADWIN/ADWIN2). https://doi.org/10.1137/1.9781611972771.42
- E. S. Page, *Continuous Inspection Schemes*, Biometrika 41 (1954), 100–115 (CUSUM/Page-Hinkley-Grundlage).
- C. Raab, M. Heusinger, F.-M. Schleif, *Reactive Soft Prototype Computing for Concept Drift Streams*, Neurocomputing 416 (2020), 340–351 (KSWIN).
- J. Gama, P. Medas, G. Castillo, P. Rodrigues, *Learning with Drift Detection*, SBIA 2004 (DDM); M. Baena-García et al., *Early Drift Detection Method* (EDDM), 2006.
- J. Gama, I. Žliobaitė, A. Bifet, M. Pechenizkiy, A. Bouchachia, *A Survey on Concept Drift Adaptation*, ACM Computing Surveys 46(4), 2014. https://doi.org/10.1145/2523813
- J. Lu, A. Liu, F. Dong, F. Gu, J. Gama, G. Zhang, *Learning under Concept Drift: A Review*, IEEE TKDE 31(12), 2019. https://doi.org/10.1109/TKDE.2018.2876857
- P. Zenisek, F. Holzinger, M. Affenzeller, *Machine Learning based Concept Drift Detection for Predictive Maintenance*, Computers & Industrial Engineering 137 (2019). https://doi.org/10.1016/j.cie.2019.106031
- river (Online ML, BSD-3). https://riverml.xyz · https://github.com/online-ml/river · river drift-API: https://riverml.xyz/latest/api/drift/ADWIN/
- scikit-multiflow (eingefroren, in river aufgegangen). https://scikit-multiflow.github.io/
- alibi-detect (BSL 1.1, v0.13.0). https://github.com/SeldonIO/alibi-detect · Seldon-Lizenzwechsel: https://www.seldon.io/strengthening-our-commitment-to-open-core/
- Frouros (BSD-3, dedizierte Drift-Library). J. Céspedes-Sisniega, Á. López-García, *Frouros: An open-source Python library for drift detection*, SoftwareX 2024. https://github.com/IFCA-Advanced-Computing/frouros

> Hinweis: Algorithmus- und Library-Bewertung nach öffentlich publizierten Methoden und dokumentiertem Stand 2025/2026. Versionsstände und Lizenztexte vor dem Bau erneut prüfen.
