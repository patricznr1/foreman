# ============================================================
#  FOREMAN — archive/__init__.py
#  Zweck: Quellenübergreifendes Archiv (Paket 1b) — die Suche über Notizen +
#         Wartung + Alarme hinter GET /api/v1/archive/search. Öffentliche Fläche:
#         das einheitliche Treffer-Modell (ArchiveHit), die Such-Funktion
#         (search_archive) und der Default-Quellen-Satz (ALL_SOURCES).
#  Architektur-Einordnung: Schicht 2. Reuse des 1a-Notiz-Hybrids (foreman.notes),
#         Wartung/Alarm reiner Volltext.
# ============================================================
from __future__ import annotations

from foreman.archive.schemas import ArchiveHit, SourceType
from foreman.archive.search import ALL_SOURCES, search_archive

__all__ = [
    "ALL_SOURCES",
    "ArchiveHit",
    "SourceType",
    "search_archive",
]
