# ============================================================
#  FOREMAN — reads/__init__.py
#  Zweck: Der geteilte, transport-neutrale Read-Core. Reine, injizierte
#         (Session) Read-only-Datenzugriffe + Status-Komposition, die ALLE
#         Transporte gemeinsam nutzen — die MCP-Schicht (F7), die HTTP-Read-
#         Routen und der WebSocket-Push-Layer (F5). Eine Wahrheit, keine
#         Duplikation: hier liegt die Logik, die Transporte rufen sie auf.
#  Architektur-Einordnung: Read-Core (Schicht 2). Hängt nur an db/models +
#         Reasonern — kennt KEINEN Transport (kein FastAPI, kein MCP, kein WS).
#         Dadurch ohne Transport-Doubles testbar.
#  Invariante: ausschließlich SELECT — keine Aktorik, kein Write, kein
#         Reasoner-/LLM-Trigger.
# ============================================================
from __future__ import annotations
