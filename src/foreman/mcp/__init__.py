# ============================================================
#  FOREMAN — mcp/__init__.py
#  Zweck: Öffentliche Schnittstelle der MCP-Schicht (F7) — FOREMAN als offener
#         Knoten. Read-only Model-Context-Protocol-Server, der die aggregierten
#         Erkenntnisse der Reasoner als saubere, maschinenlesbare Tools an
#         Drittsysteme reicht (Simulation/ERP/Energiemanagement).
#  Architektur-Einordnung: Schnittstellen-Schicht über den bestehenden Service-/
#         Read-Pfaden (Schicht 2). Erfindet keine Logik — exponiert vorhandene
#         Outputs transparent, sicher, IP-wort-diszipliniert nach außen.
#  Invarianten (Brief §2): (I) read-only, keine Aktorik, keine Reasoner-Trigger
#         über MCP. (II) AI-Act-Transparenz an jedem KI-Output (Art. 50(2)).
#         (III) kein internes Vokabular in extern sichtbaren Strings.
# ============================================================
from __future__ import annotations
