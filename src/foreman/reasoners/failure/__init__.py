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
# ============================================================
from __future__ import annotations
