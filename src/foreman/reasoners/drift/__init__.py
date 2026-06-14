# ============================================================
#  FOREMAN — reasoners/drift/__init__.py
#  Zweck: Drift-Reasoner (F4) — erkennt Verhaltensänderungen einer Maschine
#         gegen ihr eigenes historisches Profil (Concept Drift), NICHT gegen
#         statische Schwellwerte. Reine Algorithmik (river/ADWIN), kein LLM.
#  Architektur-Einordnung: erster vollständiger Reasoner. Pipeline:
#         readings_1m -> State-Gating -> Residuum/Deseasonalisierung -> ADWIN ->
#         Relevanz-Filter -> Drift-Ereignis (semantic_event + alarms-Warnung, HITL).
#  Referenz: docs/research/drift-erkennung-verfahren.md (§3 Gating, §6 ADWIN, §7 Validierung).
# ============================================================
