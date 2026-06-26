# ============================================================
#  FOREMAN — archive/schemas.py
#  Zweck: Der quellenübergreifende Archiv-Treffer-Vertrag (Paket 1b). ArchiveHit ist
#         das EINHEITLICHE Treffer-Modell über die drei Quellen (Notiz/Wartung/Alarm),
#         auf das Paket 1c (Frontend) baut.
#  Architektur-Einordnung: Schicht 2 (Pydantic-V2-Schema). Reines Anzeige-Modell.
#  Datenschutz (§8): `detail` trägt NUR PII-freie Anzeige-Attribute — KEINE
#         HMAC-Token (author/performed_by/acknowledged_by) und keine Vektoren.
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

# Die drei durchsuchbaren Archiv-Quellen.
SourceType = Literal["note", "maintenance", "alarm"]


class ArchiveHit(BaseModel):
    """Ein quellenübergreifender Archiv-Treffer (Vertrag für Paket 1c).

    `timestamp` ist quellen-normalisiert (Notiz→created_at, Wartung→performed_at,
    Alarm→raised_at). `excerpt` ist der durchsuchbare Freitext gekürzt (Notiz→text,
    Wartung→description, Alarm→message). `detail` trägt quellenspezifische, PII-freie
    Anzeige-Attribute: Notiz→{shift}; Wartung→{type}; Alarm→{severity, category, code}.
    Reihenfolge der Liste = globaler RRF-Rang; KEIN Score-Feld nach außen.
    """

    source_type: SourceType
    id: int
    machine_id: int | None
    timestamp: datetime
    excerpt: str
    detail: dict[str, Any]
