# Methodenwahl für den Ausfallvorhersage-Reasoner

> Technisches Research-Dokument · Stand Juni 2026
> Scope: Wahl von Problem-Framing, Modell, Imbalance-Strategie, Validierung und Erklärbarkeits-Schnittstelle für den **Ausfallvorhersage-Reasoner** von FOREMAN. Das klassische ML-Modell läuft in FOREMAN selbst; seine Ausgabe wird von einem LLM (über das interne Modell-Gateway) in eine Empfehlung übersetzt.
> Datencharakteristik: stark unbalanciert (Ausfälle selten), begrenzte Historie, gemischte Feature-Typen (aus Zeitreihen abgeleitete numerische Features + kategoriale Metadaten).
> Datenquellen (FOREMAN-Schema): `readings` bzw. die Continuous Aggregates `readings_1m/1h` (Sensorverläufe), `maintenance_events` (Wartung/Reparatur), `alarms` (Störungen), `machines`/`components`/`data_points` (Metadaten).
> Der externe Gedächtnis-Dienst ist Black Box hinter HTTP-API und hier **nicht** Gegenstand.

---

## 1. Fragestellung

Der Drift-Reasoner beantwortet „hat sich das Verhalten verschoben?". Der Ausfallvorhersage-Reasoner geht einen Schritt weiter: **„Wie wahrscheinlich fällt diese Maschine/Komponente in einem definierten Zeitfenster aus?"** Das ist prognostisch, braucht historisches Ausfallwissen als Wahrheit und ist damit das datenhungrigste der vier Reasoner — in einer Realität, in der echte Ausfälle selten und die Historie kurz ist.

Das Dokument klärt sechs Fragen: Problem-Framing (2), Modellfamilien (3), Klassen-Ungleichgewicht (4), Feature-Engineering (5), Validierung bei Datenknappheit (6), Erklärbarkeits-Schnittstelle zum LLM (7). Abschnitt 8 benennt die getroffene Wahl mit Code; Tradeoffs stehen in den Vergleichstabellen davor.

Leitlinie über allem: FOREMAN ist **Human-in-the-Loop** und aktoriert nie. Eine Ausfallwahrscheinlichkeit ist eine **Entscheidungsunterstützung**, keine Steuerungsgröße. Das prägt Metrikwahl (lieber sensibel mit erklärbarem Grund als hochpräzise und stumm) und Erklärbarkeitspflicht.

---

## 2. Problem-Framing

Drei Framings konkurrieren. Sie unterscheiden sich darin, was das Label ist und wie sie mit **Zensierung** umgehen (eine Maschine, die *noch nicht* ausgefallen ist, ist keine „negative" Beobachtung — ihr Ausfall liegt nur jenseits des Beobachtungsfensters; statistisch: rechtszensiert).

| Framing | Label | Output | Stärken | Schwächen für FOREMAN |
|---|---|---|---|---|
| **Binär-Klassifikation, fixes Horizont** („Ausfall in nächsten X Tagen?") | 1, wenn Ausfall im Fenster nach Stichtag | Ausfallwahrscheinlichkeit ∈ [0,1] | einfach, direkt aktionierbar, robust bei wenig Daten, SHAP-/LLM-freundlich | Horizont X willkürlich; behandelt zensierte Fälle als „kein Ausfall" (leichte Verzerrung) |
| **Regression auf RUL** (Restlebensdauer) | verbleibende Zeit/Zyklen bis Ausfall | Zahl (Tage/Zyklen) | informativ für Planung | braucht **run-to-failure**-Verläufe (genau das, was fehlt); zensierte Maschinen unbenutzbar oder verzerren |
| **Survival / Time-to-Event** (Cox, RSF, GBSA, Weibull) | (Zeit, Ereignis-Flag) | Überlebens-/Hazardkurve über Zeit | nutzt **zensierte** Beobachtungen korrekt; liefert Risiko über mehrere Horizonte | komplexer, erklärungs- und LLM-seitig anspruchsvoller, kleinere Tool-Ökosysteme |

Für die **Industrie-Realität von FOREMAN** gilt: RUL-Regression ist am attraktivsten klingend, aber am datenhungrigsten — sie verlangt viele vollständige Verläufe von „gesund" bis „kaputt", die bei seltenen Ausfällen und kurzer Historie schlicht nicht da sind. Survival ist die **statistisch ehrlichste** Form (sie verschwendet die vielen *nicht* ausgefallenen Maschinen nicht), aber die schwerste, sauber zu validieren und dem LLM verständlich zu übergeben. Binär-Klassifikation auf festem Horizont ist das **robusteste MVP**: ein Stichtag, ein Blick X Tage voraus, ein Wahrscheinlichkeitswert, der direkt in eine HITL-Empfehlung mündet — und der sich mit wenig Labels noch trainieren und mit SHAP erklären lässt.

**Entscheidung des Framings:** binäre Klassifikation auf festem Horizont als MVP, mit Survival (GBSA) als dokumentiertem Phase-2-Upgrade, sobald genug zensierte Historien vorliegen (Begründung in 8).

---

## 3. Modellfamilien im Vergleich

| Modellfamilie | Datenbedarf | Erklärbarkeit | Umgang mit Imbalance | Eignung Klassifikation / RUL / Survival | Gemischte Features |
|---|---|---|---|---|---|
| **Gradient Boosting** (XGBoost, LightGBM, CatBoost) | gering–mittel | hoch (SHAP TreeExplainer, exakt) | `scale_pos_weight`/Class-Weights, Custom-Loss | Klassifikation ★★★ · RUL ★★ (Regr.) · Survival ★★ (GBSA) | nativ (LightGBM/CatBoost: Kategorien + NaN) |
| **Random Forest** | gering–mittel | hoch (SHAP, Importances) | `class_weight='balanced'` | Klassifikation ★★ · RUL ★ · Survival ★★ (RSF) | gut |
| **Survival-Modelle** (Cox, RSF, GBSA, Weibull) | mittel | mittel (Cox-Koeff. interpretierbar; RSF/GBSA via SHAP eingeschränkt) | implizit über Zensierung | Survival ★★★ · Risiko über Horizonte | Cox: kategorial via Encoding; RSF/GBSA: gut |
| **Einfache Baselines** (Logistische Regression, Schwellwert-Heuristik) | sehr gering | sehr hoch | Class-Weights | Klassifikation ★ | manuell (Encoding/Scaling) |
| **Deep Learning** (LSTM/CNN/Transformer auf Rohzeitreihe) | **hoch** | gering (post-hoc, teuer) | Loss-Gewichtung | RUL ★★★ bei viel Run-to-Failure | braucht eigene Pipelines |

**Lesart.** Deep Learning fällt für FOREMANs Datenlage aus — es glänzt bei großen Run-to-Failure-Beständen (z. B. C-MAPSS-Benchmarks), nicht bei wenigen realen Ausfällen; zudem teuer erklärbar. Survival-Modelle (insb. **Gradient Boosting Survival Analysis, GBSA**) sind in aktuellen PdM-Vergleichen die robusteste Survival-Variante, aber zweite Wahl fürs MVP wegen Erklär-/LLM-Aufwand. **Gradient-Boosted Decision Trees** sind der Sweet Spot: stark bei tabellarischen, gemischten Features, robust bei wenig Daten, native Behandlung fehlender Werte und Kategorien (LightGBM/CatBoost), und — entscheidend für den LLM-Layer — über **TreeExplainer exakt und billig per SHAP erklärbar**. Random Forest ist die solide, etwas schwächere Alternative; einfache Baselines bleiben als Pflicht-Referenz, gegen die das Boosting seinen Mehrwert beweisen muss.

---

## 4. Umgang mit Klassen-Ungleichgewicht

Bei seltenen Ausfällen ist **Accuracy wertlos** (ein Modell, das nie „Ausfall" sagt, hat 99 % Accuracy und null Nutzen). Zwei Fragen sind zu trennen: *Wie trainiert man?* und *Wie misst und entscheidet man?*

**Training — Class-Weights statt SMOTE.** Für Gradient Boosting ist die saubere, kalibrierungsfreundliche Lösung die **Kostengewichtung der Minderheitsklasse** (`scale_pos_weight` ≈ #negativ/#positiv bzw. `class_weight`), nicht synthetisches Oversampling. Aktuelle Vergleiche auf tabellarischen, imbalancierten Daten zeigen, dass SMOTE und Varianten gegenüber Class-Weights bei Boosting selten gewinnen, dafür aber die **Wahrscheinlichkeits-Kalibrierung verschlechtern** und synthetisches Rauschen einschleppen können — gerade bei extremem Ungleichgewicht heikel. SMOTE bleibt eine Option für Experimente, ist aber nicht der Default. Synthetische *Minderheits*daten kommen in FOREMAN besser aus dem digitalen Zwilling (echte Degradationsphysik) als aus SMOTE-Interpolation (siehe 6).

**Messen — PR-Kurve statt ROC.** Bei starkem Ungleichgewicht ist **PR-AUC (Average Precision)** die aussagekräftige Kennzahl; ROC-AUC wirkt durch die große Negativklasse zu optimistisch. Operativ zählt **Recall bei akzeptabler Precision** (jeder verpasste Ausfall ist teuer, aber Alarmmüdigkeit zerstört Vertrauen).

**Entscheiden — Schwellwert kostensensitiv setzen, nicht 0,5.** Der Klassifikations-Schwellwert wird nicht auf den Default 0,5 gelassen, sondern auf der PR-Kurve so gewählt, dass ein **Ziel-Recall bei vertretbarer Precision** erreicht wird — idealerweise mit den realen Kosten (verpasster Ausfall vs. unnötige Inspektion) gewichtet. Dieser Schwellwert ist ein bewusster, dokumentierter Betriebsparameter, kein Modell-Detail.

---

## 5. Feature-Engineering aus Sensorzeitreihen

Etablierte, bei Predictive Maintenance bewährte Feature-Gruppen — alle **zum Vorhersagezeitpunkt berechenbar** (keine Zukunftsinformation, siehe Leakage in 6):

- **Roll-Statistiken** über mehrere Fenster (z. B. 1 h / 24 h / 7 d): Mittel, Std, Min, Max, RMS, Median, Interquartilsabstand pro `data_point`. RMS und Std sind klassische Verschleiß-Indikatoren bei Vibration.
- **Trend-/Drift-Features:** Steigung einer linearen Regression über das Fenster, Differenz kurzes vs. langes Mittel — **und direkt das Output-Signal des Drift-Reasoners** (Drift erkannt ja/nein, Zeit seit letzter Drift). Das koppelt die beiden Reasoner sinnvoll: Drift ist ein Frühindikator, der hier als Feature eingeht.
- **Rate-of-Change / Lag-Features:** erste Differenz, prozentuale Änderung, Lag-Werte (Wert vor 1 h/24 h).
- **Frequenz-Features** (wo hochfrequente Vibration vorliegt): Bandenergien aus FFT, dominante Frequenz, Spektral-Kurtosis — sensibel für Lager-/Unwucht-Signaturen. Nur sinnvoll, wenn die Abtastrate das hergibt.
- **Ereignis-/Kontext-Features:** Zeit seit letzter Wartung (`maintenance_events.performed_at`), Anzahl Alarme im Fenster (`alarms`), Betriebsstunden/Zyklen, kumulierte Last.
- **Kategoriale Metadaten:** `machines.type`/`manufacturer`/`model`, `components.component_type`, `data_points.measurement_type`. LightGBM/CatBoost verarbeiten diese nativ (kein One-Hot-Zwang).

**Quelle der Features: die Continuous Aggregates** (`readings_1m`/`1h`) statt der Rohtabelle — die Roll-Statistiken liegen dort bereits vor bzw. lassen sich billig darauf rechnen, was Feature-Bau und Insert-Last entkoppelt. `tsfresh` ist für die explorative Feature-Suche nützlich, im Produktivpfad aber gegen eine kuratierte, leakage-geprüfte Feature-Liste einzutauschen (tsfresh erzeugt Hunderte Features — Overfitting- und Leakage-Risiko bei wenig Labels).

---

## 6. Validierung bei Datenknappheit

Der gefährlichste Fehler in Predictive Maintenance ist nicht das falsche Modell, sondern **optimistische Validierung durch Leakage**. Drei Disziplinen:

1. **Zeitbasierte Splits, niemals random.** Trainings­daten liegen zeitlich **vor** den Test­daten (Stichtag-Logik). Random-K-Fold mischt Zukunft in die Vergangenheit und liefert systematisch zu gute Zahlen. Für Tuning: rollierende/expandierende Fenster (Walk-forward) statt Standard-CV.
2. **Gruppen-Bewusstsein.** Kein Datensatz derselben Maschine darf gleichzeitig in Train und Test liegen, wenn Features über Maschinen-Identität korrelieren — sonst „erkennt" das Modell die Maschine, nicht den Verschleiß. Split nach Zeit **und** ggf. nach Maschine prüfen.
3. **Feature-Leakage ausschließen.** Jedes Feature nur aus Daten bauen, die zum Vorhersagezeitpunkt real vorlagen; keine zielabgeleiteten Größen, keine über den Stichtag hinausreichenden Fenster, Normalisierungs-Statistiken nur aus Trainingsdaten.

**Gegen den Labelmangel** (wenige echte Ausfälle):

- **Transfer über Maschinenklassen:** Maschinen gleichen Typs poolen, `machine.type`/`component_type` als Feature führen — ein Modell pro Maschinenklasse statt pro Einzelmaschine. So summieren sich seltene Ausfälle über die Flotte.
- **Synthetische Daten aus dem digitalen Zwilling:** Degradations-Szenarien aus den SPS-abgeleiteten Simulationen erzeugen *physikalisch* plausible Ausfallverläufe (besser als SMOTE-Interpolation). **Pflicht:** klar als synthetisch kennzeichnen und **final immer auf echten Daten validieren** — synthetische Daten dürfen trainieren, aber nicht die Abnahme bestehen.
- **Schwache Labels:** `maintenance_events` (Reparatur/Austausch) und kritische `alarms` als Ausfall-Proxy nutzen, solange echte `failure`-Labels rar sind — mit dem Bewusstsein, dass „Wartung" ≠ „Ausfall" ist (Label-Rauschen dokumentieren).
- **Konservativ bleiben:** Bei sehr wenigen Ausfällen ehrlich ein **kalibriertes Risiko-Ranking** liefern („diese 5 Komponenten zuerst prüfen") statt eine scheingenaue Wahrscheinlichkeit. Unsicherheit gehört in den Output.

---

## 7. Erklärbarkeits-Schnittstelle zum LLM

Der LLM-Layer übersetzt das Modellergebnis in eine Klartext-Empfehlung. Er bekommt dafür **strukturierte SHAP-Werte**, keine rohen Features. SHAP (TreeExplainer) liefert für Tree-Modelle exakte, additive Beitragswerte pro Feature und Vorhersage — ideal als maschinenlesbare Begründung.

**Format (Vorschlag) — kompaktes JSON, das das Gateway an den LLM gibt:**

```json
{
  "machine_id": 42, "component_id": 7,
  "horizon_days": 14,
  "failure_probability": 0.78,
  "decision_threshold": 0.45,
  "decision": "elevated_risk",
  "model_version": "lgbm-clf-2026.06",
  "top_factors": [
    {"feature": "vibration_rms_24h", "value": 4.7, "shap": 0.31, "direction": "increases_risk"},
    {"feature": "days_since_maintenance", "value": 190, "shap": 0.18, "direction": "increases_risk"},
    {"feature": "drift_detected_recent", "value": 1, "shap": 0.12, "direction": "increases_risk"},
    {"feature": "temp_mean_24h", "value": 61.2, "shap": -0.05, "direction": "decreases_risk"}
  ],
  "data_caveats": ["limited_failure_history", "weak_labels_from_maintenance_events"]
}
```

**Grenzen, die im Prompt und im UI verankert sein müssen:**

- SHAP zeigt **Assoziation, nicht Kausalität.** Der LLM darf „erhöht das Risikomodell-Signal" formulieren, nicht „verursacht den Ausfall". Diese Grenze gehört in die System-Instruktion des Erklär-Layers.
- Der LLM **erfindet keine Werte** — er verbalisiert ausschließlich die übergebenen `top_factors` und `caveats`. (Red-Teaming gegen Halluzination ist ohnehin als Quality-Gate verankert.)
- **AI-Act-Transparenz:** Der erzeugte Text ist als KI-Output zu kennzeichnen; die Empfehlung ist Entscheidungsunterstützung, die Quittierung bleibt beim Operator (HITL).
- Unsicherheit (`data_caveats`) muss in die Formulierung durchschlagen — bei dünner Datenlage vorsichtiger Ton, kein Scheinwissen.

---

## 8. Empfehlung für FOREMAN

**Framing:** Binäre Klassifikation auf festem Vorhersagehorizont (Start: **14 Tage**, pro Maschinenklasse parametrierbar). Survival via GBSA (`scikit-survival` 0.27) ist der dokumentierte **Phase-2-Pfad**, sobald genügend zensierte Historien vorliegen — er nutzt nicht-ausgefallene Maschinen statistisch korrekt; fürs MVP überwiegt die Einfachheit, Robustheit und LLM-Tauglichkeit der Klassifikation.

**Modell & Library:** **LightGBM 4.6** (`LGBMClassifier`). Begründung: native Behandlung kategorialer Metadaten und fehlender Werte, stark bei wenig tabellarischen Daten, schnell, und exakt per **SHAP 0.52 TreeExplainer** erklärbar. CatBoost (aktuell gepflegt) ist die Ausweichoption, falls kategoriale Metadaten dominieren und das Tuning-Budget minimal ist; XGBoost 3.2 ist gleichwertig nutzbar. Eine logistische Regression mit Class-Weights läuft als Pflicht-Baseline mit.

**Imbalance:** `scale_pos_weight = #negativ/#positiv` (Class-Weights), **kein SMOTE** im Default. Synthetische Minderheitsdaten — wenn überhaupt — aus dem digitalen Zwilling, nicht aus Interpolation.

**Metrik & Schwellwert:** Primär **PR-AUC (Average Precision)**, operativ **Recall bei Ziel-Precision**; Schwellwert kostensensitiv auf der PR-Kurve gesetzt (Start: Recall ≥ 0,80 bei maximaler Precision), nicht 0,5.

**Validierung:** zeitbasierter Holdout (Train < Stichtag < Test) plus walk-forward für Tuning; maschinengruppen-bewusst; strikte Leakage-Prüfung; synthetische Daten dürfen trainieren, die Abnahme läuft auf echten Ausfällen.

**Features:** kuratierte Liste aus Roll-Statistiken (1 h/24 h/7 d), Trend/Slope, Rate-of-Change, Zeit seit Wartung, Alarm-Zähler, **Drift-Reasoner-Output**, kategoriale Stammdaten — bezogen aus den Continuous Aggregates.

**Erklärbarkeit:** SHAP-TreeExplainer → strukturiertes JSON (Abschnitt 7) an den LLM über das interne Gateway; SHAP = assoziativ, AI-Act-Kennzeichnung, HITL.

### 8.1 Kopierbares Code-Snippet (Modell-Setup + zeitbasierter Split + SHAP-Ausgabe fürs LLM)

```python
# foreman/reasoners/failure/train.py
"""Ausfallvorhersage: binaere Klassifikation auf festem Horizont.
LightGBM (4.6) + Class-Weights + PR-AUC + zeitbasierter Split + SHAP fuers LLM.
Klassisches ML laeuft in FOREMAN; das LLM kommt separat ueber das interne Gateway."""
from __future__ import annotations
import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import average_precision_score, precision_recall_curve

HORIZON_DAYS = 14
CATEGORICAL = ["machine_type", "component_type", "measurement_type"]


def time_based_split(df: pd.DataFrame, cutoff: pd.Timestamp):
    """Train liegt VOR dem Stichtag, Test danach. Kein random split (Leakage!)."""
    train = df[df["asof_time"] < cutoff]
    test = df[df["asof_time"] >= cutoff]
    return train, test


def train_failure_model(df: pd.DataFrame, cutoff: pd.Timestamp):
    train, test = time_based_split(df, cutoff)
    feats = [c for c in df.columns if c not in ("label", "asof_time", "machine_id", "component_id")]
    X_tr, y_tr = train[feats], train["label"]
    X_te, y_te = test[feats], test["label"]

    for c in CATEGORICAL:
        if c in X_tr.columns:
            X_tr[c] = X_tr[c].astype("category")
            X_te[c] = X_te[c].astype("category")

    # Imbalance ueber Class-Weights, NICHT SMOTE:
    pos = int(y_tr.sum()); neg = int(len(y_tr) - pos)
    scale_pos_weight = max(neg / max(pos, 1), 1.0)

    model = lgb.LGBMClassifier(
        objective="binary", n_estimators=600, learning_rate=0.03,
        num_leaves=31, min_child_samples=40, subsample=0.8,
        colsample_bytree=0.8, reg_lambda=1.0,
        scale_pos_weight=scale_pos_weight, random_state=42,
    )
    model.fit(X_tr, y_tr, categorical_feature=CATEGORICAL)

    # Metrik: PR-AUC (Average Precision), nicht Accuracy/ROC bei starkem Imbalance.
    proba = model.predict_proba(X_te)[:, 1]
    pr_auc = average_precision_score(y_te, proba)

    # Schwellwert kostensensitiv: kleinster Threshold mit Recall >= Ziel.
    prec, rec, thr = precision_recall_curve(y_te, proba)
    target_recall = 0.80
    ok = np.where(rec[:-1] >= target_recall)[0]
    threshold = float(thr[ok[np.argmax(prec[ok])]]) if len(ok) else 0.5
    return model, feats, {"pr_auc": float(pr_auc), "threshold": threshold}


def explain_for_llm(model, feats, row: pd.DataFrame, meta: dict, threshold: float) -> dict:
    """Erzeugt das strukturierte SHAP-JSON, das der LLM-Erkaer-Layer verarbeitet."""
    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(row[feats])
    contrib = sv[1][0] if isinstance(sv, list) else sv[0]  # positive Klasse
    proba = float(model.predict_proba(row[feats])[:, 1][0])
    order = np.argsort(np.abs(contrib))[::-1][:5]
    top = [{
        "feature": feats[i], "value": float(row[feats].iloc[0, i]),
        "shap": round(float(contrib[i]), 4),
        "direction": "increases_risk" if contrib[i] > 0 else "decreases_risk",
    } for i in order]
    return {
        "machine_id": meta["machine_id"], "component_id": meta.get("component_id"),
        "horizon_days": HORIZON_DAYS, "failure_probability": round(proba, 3),
        "decision_threshold": round(threshold, 3),
        "decision": "elevated_risk" if proba >= threshold else "normal",
        "model_version": "lgbm-clf-2026.06", "top_factors": top,
        "data_caveats": meta.get("caveats", []),
    }
```

---

## 9. Offene Punkte

- **Ausfall-Label-Definition.** Was genau ist ein „Ausfall" — ungeplanter Stillstand, `alarm` einer Kategorie, `maintenance_event` vom Typ Reparatur? Die Label-Quelle bestimmt Qualität und Vergleichbarkeit; mit den realen SPS-/Wartungsdaten festzulegen (ggf. eigene `failure_events`-Erfassung).
- **Horizont X final.** 14 Tage ist Startwert; betrieblich sinnvoll ist der Vorlauf, der eine geplante Wartung erlaubt — pro Maschinenklasse zu kalibrieren, ggf. mehrere Horizonte.
- **Phase-2 Survival (GBSA).** Ab welcher Menge zensierter Historien lohnt der Wechsel/das Ergänzen um ein Survival-Modell? Kriterium und Trigger definieren.
- **Kalibrierung der Wahrscheinlichkeiten.** Class-Weights verzerren die Roh-Wahrscheinlichkeit; falls der LLM/Operator absolute Wahrscheinlichkeiten interpretiert, Kalibrierung (z. B. Isotonic/Platt auf einem Holdout) nachrüsten.
- **Drift-Feature-Kopplung.** Genaue Form des Drift-Outputs als Feature (binär, Zeit seit Drift, Drift-Magnitude) am realen Reasoner-Output festmachen.
- **Synthetik-Anteil.** Wie viel digitaler-Zwilling-Anteil im Training ist vertretbar, ohne die Realvalidierung zu verzerren? Empirisch begrenzen.
- **Modell-Lifecycle.** Re-Training-Trigger (neue Ausfälle, Daten-Drift im Feature-Raum), Versionierung, Monitoring der Live-PR-AUC — in die Observability (`/metrics`) aufnehmen.

---

## Quellen

- Surveys Predictive Maintenance / Prognostics (2024/2025): *A Survey of Predictive Maintenance Methods: Prognostics via Classification and Regression* (2025); *Predictive maintenance in Industry 4.0: a survey of planning models and ML techniques* (2024, PMC11157603); *Weak Supervision: A Survey on Predictive Maintenance*, WIREs DMKD (2025); *A Comprehensive Survey on Deep Learning-based Predictive Maintenance*, ACM TECS (2025).
- Survival/PdM: *Survival Analysis-Based System for Predictive Maintenance Optimization*, SN Computer Science (2025) — GBSA als robusteste Survival-Variante. scikit-survival (GBSA/RSF/Cox), v0.27. https://scikit-survival.readthedocs.io/
- Imbalanced Learning: N. Chawla et al., *SMOTE*, JAIR 16 (2002); H. He, E. Garcia, *Learning from Imbalanced Data*, IEEE TKDE (2009); *CLIMB: Class-imbalanced Learning Benchmark on Tabular Data* (2025, arXiv:2505.17451); empirische Vergleiche Class-Weights vs. SMOTE bei Boosting (2024/2025). PR-AUC: Saito & Rehmsmeier, *The Precision-Recall Plot…*, PLOS ONE (2015).
- Gradient Boosting Libraries: XGBoost 3.2 (Feb 2026) https://xgboost.readthedocs.io/ · LightGBM 4.6 https://lightgbm.readthedocs.io/ · CatBoost https://catboost.ai/ · Ke et al., *LightGBM*, NeurIPS 2017; Prokhorenkova et al., *CatBoost*, NeurIPS 2018.
- Erklärbarkeit: Lundberg & Lee, *A Unified Approach to Interpreting Model Predictions* (SHAP), NeurIPS 2017; Lundberg et al., *Consistent Individualized Feature Attribution / TreeExplainer*, Nature MI (2020). SHAP 0.52. https://shap.readthedocs.io/
- Feature-Engineering: Christ et al., *tsfresh* (2018) https://tsfresh.readthedocs.io/ · NASA C-MAPSS Turbofan (RUL-Benchmark). Validierung/Leakage: Zeit-basierte CV / Walk-forward (Praxisliteratur 2025/2026).

> Hinweis: Modell- und Library-Empfehlung nach publizierten Methoden und dokumentiertem Stand 2025/2026. Versions- und API-Stände vor dem Bau gegen die eingesetzten Pakete prüfen.
