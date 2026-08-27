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

from pydantic import BaseModel, Field

# Die drei durchsuchbaren Archiv-Quellen.
# "memory" ist die vierte Quelle (Substrat-Veredelung): ein Treffer aus dem
# Gedaechtnis statt aus der eigenen Datenbank. Eigener Wert, weil die Herkunft
# sichtbar bleiben muss — als note oder alarm getarnt waere er eine Behauptung
# ueber die eigene Datenlage, die nicht stimmt.
SourceType = Literal["note", "maintenance", "alarm", "memory"]


class ArchiveHit(BaseModel):
    """Ein quellenübergreifender Archiv-Treffer (Vertrag für Paket 1c).

    `timestamp` ist quellen-normalisiert (Notiz→created_at, Wartung→performed_at,
    Alarm→raised_at). `excerpt` ist der durchsuchbare Freitext gekürzt (Notiz→text,
    Wartung→description, Alarm→message). `detail` trägt quellenspezifische, PII-freie
    Anzeige-Attribute: Notiz→{shift}; Wartung→{type}; Alarm→{severity, category, code};
    Gedaechtnis→{herkunft} plus, falls bekannt, {quelle: {art, id}} als Rueckweg auf
    die Zeile, aus der die Erinnerung entstand. Fuer Altbestand fehlt dieser Rueckweg —
    er wird NICHT geraten (siehe substrate/backfill.py::herkunft_ergaenzen).
    Reihenfolge der Liste = globaler RRF-Rang; KEIN Score-Feld nach außen.

    `source_type` sagt, WAS der ausgelieferte Treffer ist. `gefunden_von` sagt,
    WELCHE Quellen ihn gefunden haben — beides kann auseinanderfallen, seit die
    Fusion denselben Vorgang aus mehreren Ranglisten zusammenführt: Eine Notiz,
    die auch das Gedächtnis kennt, kommt als `note` mit `["note", "memory"]`. Das
    ist die einzige Stelle, an der Einigkeit zwischen Quellen nach außen sichtbar
    wird; ohne sie sähe ein bestätigter Treffer aus wie ein Einzelfund.
    """

    source_type: SourceType
    id: int
    machine_id: int | None
    timestamp: datetime
    excerpt: str
    detail: dict[str, Any]
    # Leer nur, solange ein Treffer nicht durch die Fusion gelaufen ist (Bau in
    # `_note_hit` & Co.). Was `search_archive` ausliefert, trägt IMMER mindestens
    # eine Quelle — `tests/archive/test_fusion.py` fordert das ein.
    gefunden_von: list[SourceType] = Field(default_factory=list)
