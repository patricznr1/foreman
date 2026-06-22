# ============================================================
#  FOREMAN — topology/schemas.py (Sektion I)
#  Zweck: Lese-Verträge der Systemtopologie. Ein Knoten trägt Typ, Datenrichtung,
#         ehrlichen Status und (wo messbar) die letzte Aktivität. Status-/Richtungs-
#         Werte sind die deutschen Domänen-Vokabeln der Studie (FCSM-konsistent).
#  Architektur-Einordnung: Topologie-Schicht (Schicht 2).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TopologyNode(BaseModel):
    """Ein Topologie-Knoten — eine real abgeleitete (oder als [VISION] markierte) Quelle/Senke."""

    id: str
    label: str
    # kind: ingest_source | substrate | mcp_boundary | vision
    kind: str
    # direction: liefert | liest | beides | keine
    direction: str
    # status: verbunden | gestört | inaktiv | unbekannt (nie grün geraten)
    status: str
    last_activity: datetime | None = None
    # internal=True markiert die interne Simulationsquelle (kein externer Peer).
    internal: bool = False
    # vision=True markiert ein illustratives, NICHT verbundenes [VISION]-Drittsystem.
    vision: bool = False
    detail: dict[str, Any] | None = None


class TopologyView(BaseModel):
    """Die Systemtopologie: real abgeleitete Knoten + die separate [VISION]-Kategorie."""

    nodes: list[TopologyNode]
    vision: list[TopologyNode]
    generated_at: datetime
