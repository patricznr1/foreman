# ============================================================
#  FOREMAN — ingestion/adapter.py
#  Zweck: Adapter-Plugin-Interface (SourceAdapter) — die EINZIGE Schnittstelle,
#         die die Ingestion kennt. Kein Protokoll-/Simulationswissen oberhalb
#         des Adapters.
#  Architektur-Einordnung: Ingestion (Schicht 2). Konkrete Adapter (Simulation
#         in F3; OPC UA/MQTT/Modbus später) erben hiervon und liefern den
#         normalisierten Reading-/Event-Strom.
# ============================================================
from __future__ import annotations

import heapq
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from foreman.ingestion.normalized import NormalizedEvent, NormalizedReading

# Ein Element des vereinheitlichten Quell-Stroms: Messwert ODER diskretes Ereignis.
StreamItem = NormalizedReading | NormalizedEvent


def stream_item_time(item: StreamItem) -> datetime:
    """Maßgeblicher Zeitstempel eines Strom-Elements (für die zeitliche Mischung)."""
    if isinstance(item, NormalizedReading):
        return item.time
    return item.occurred_at


class SourceAdapter(ABC):
    """Abstrakte Datenquelle: liefert normalisierte Readings/Events an die Ingestion.

    Lebenszyklus: erst `seed_topology` (idempotent; legt Linien/Maschinen/
    Komponenten/Datenpunkte an und merkt sich die ID-Auflösung intern), dann
    `readings()`/`events()` — beide nach Zeit sortiert. `stream()` mischt sie
    lazy zu einem zeitlich geordneten Gesamtstrom (Default-Implementierung).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Eindeutiger Adapter-Name (z. B. 'simulation') — Registry-Schlüssel."""

    @abstractmethod
    async def seed_topology(self, session: AsyncSession) -> None:
        """Legt die Quell-Topologie idempotent an (vor dem ersten Streaming)."""

    @abstractmethod
    def readings(self) -> Iterable[NormalizedReading]:
        """Normalisierte Messwerte, aufsteigend nach `time` sortiert."""

    @abstractmethod
    def events(self) -> Iterable[NormalizedEvent]:
        """Normalisierte diskrete Ereignisse, aufsteigend nach `occurred_at`."""

    def stream(self) -> Iterator[StreamItem]:
        """Mischt Readings + Events lazy zu einem zeitlich sortierten Strom.

        Voraussetzung: `readings()` und `events()` sind je für sich sortiert.
        `heapq.merge` zieht beide Quellen verschränkt, ohne alles in den Speicher
        zu laden — wichtig für große Backfill-Läufe.
        """
        return heapq.merge(self.readings(), self.events(), key=stream_item_time)
