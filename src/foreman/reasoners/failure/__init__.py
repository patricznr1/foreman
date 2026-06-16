# ============================================================
#  FOREMAN — reasoners/failure/ (F-PRED, Ausfallvorhersage-Reasoner)
#  Zweck: Ausfallwahrscheinlichkeit je Maschine über klassisches ML (LightGBM)
#         + SHAP-Faktor-Attribution. Pipeline: Feature-Extraktion (rein) →
#         Trainingsdatensatz aus Szenarien → Offline-Training (CLI) → Inferenz
#         (Artefakt laden + predict + SHAP) → persistierte FailurePrediction.
#  Architektur-Einordnung: Reasoning-Schicht (Reasoner #3, §2 GROUND_TRUTH).
#
#  EHRLICH DEKLARIERTER METHODEN-DEMONSTRATOR (Kern-Anliegen, §16):
#         Dieses Modul ist auf SIMULATIONSDATEN trainiert. Es gibt über den
#         verfügbaren Daten-Kanal (SPS-Programme, keine Logs) grundsätzlich keine
#         realen Run-to-failure-Historien — die Pipeline ist technisch
#         VERIFIZIERBAR, aber ohne reale Ground Truth NICHT VALIDIERBAR. Der
#         Vorbehalt ist strukturell erzwungen: jede FailurePrediction trägt
#         `validation_status=simulation_only` als Pflichtfeld (schema.py), jede
#         Metrik das Label `data_regime=simulation`. Begründung im Detail:
#         docs/models/failure_prediction_model_card.md.
#
#  F-REC (Erklär-Layer, zweiter Modul-Teil): die LLM-Werker-Empfehlung über einer
#         FailurePrediction (recommendation.py + recall.py + grounding.py + prompts.py).
#         Zweiter Konsument des LLM-Gateways nach F6. Zwei Invarianten: (I) Zahlen
#         autoritativ vom Modell (numerischer Post-Check rejectet erfundene Zahlen),
#         (II) deterministischer Sim-Vorbehalt (validation_caveat, nie LLM-generiert).
# ============================================================
from __future__ import annotations
