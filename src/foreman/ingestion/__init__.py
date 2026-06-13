# ============================================================
#  FOREMAN — ingestion/__init__.py
#  Zweck: Protokoll-agnostische Datenakquise-Schicht (F3).
#  Architektur-Einordnung: Ingestion (Schicht 2). Bündelt das interne
#         Normalformat, das Adapter-Interface, die Registry und den
#         IngestionService. Oberhalb des Adapters existiert kein Wissen über
#         das Quellprotokoll (OPC UA/MQTT/Simulation) — alles fließt als
#         NormalizedReading/NormalizedEvent in den Service.
# ============================================================
from __future__ import annotations

from foreman.ingestion.normalized import (
    AlarmEvent,
    EventKind,
    MaintenanceRecord,
    NormalizedEvent,
    NormalizedReading,
    ProductionRunRecord,
    WorkerNoteRecord,
)

__all__ = [
    "AlarmEvent",
    "EventKind",
    "MaintenanceRecord",
    "NormalizedEvent",
    "NormalizedReading",
    "ProductionRunRecord",
    "WorkerNoteRecord",
]
