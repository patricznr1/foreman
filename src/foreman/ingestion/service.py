# ============================================================
#  FOREMAN — ingestion/service.py
#  Zweck: IngestionService (F3) — konsumiert die normalisierte Ausgabe eines
#         SourceAdapters: batcht Readings und schreibt sie über den F2-COPY-Pfad
#         in `readings`; schreibt diskrete Ereignisse (Alarme, Produktionslauf-
#         Grenzen, Wartungsereignisse, Werker-Notizen) in ihre Tabellen; spiegelt
#         semantische Ereignisse best-effort ans Substrat (+ semantic_events).
#  Architektur-Einordnung: Ingestion (Schicht 2). Adapter-agnostisch — kennt nur
#         das SourceAdapter-Interface und das Normalformat.
#  Datenschutz (§8): Personen-Felder laufen durch den F2-Schreibpfad —
#         worker_notes.text NER-maskiert, worker_notes.author und
#         maintenance_events.performed_by tokenisiert (HMAC). Kein Klartext.
#  COPY-Pfad: `copy_readings` ist der EINZIGE Reading-Schreibweg (Research §3.4)
#         und wird auch vom POST /api/v1/readings-Router genutzt — kein zweiter Weg.
#  Embedding (F-SEM, §15): Werker-Notizen werden vor jedem Commit als EIN Batch
#         eingebettet (best-effort) — Provider-Ausfall → embedding=NULL, der
#         Backfill holt es nach; der Notiz-Schreibpfad blockiert NIE auf dem
#         Embedding.
# ============================================================
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from foreman.core.pseudonymize import Pseudonymizer
from foreman.core.redact import Redactor
from foreman.db.models import Alarm, MaintenanceEvent, ProductionRun, WorkerNote
from foreman.embeddings import EmbeddingProvider, embed_best_effort
from foreman.ingestion.adapter import SourceAdapter, stream_item_time
from foreman.ingestion.normalized import (
    AlarmEvent,
    MaintenanceRecord,
    NormalizedEvent,
    NormalizedReading,
    ProductionRunRecord,
    WorkerNoteRecord,
)
from foreman.ingestion.semantic import record_semantic_event
from foreman.realtime.channels import ChangeSet
from foreman.realtime.notify import notify_changes
from foreman.substrate.client import SubstrateClient

logger = logging.getLogger("foreman.ingestion.service")

# Spaltenreihenfolge des COPY-Streams (muss zur readings-Tabelle passen).
COPY_COLUMNS = ["time", "data_point_id", "value", "quality"]

# Eine COPY-Zeile: (time, data_point_id, value, quality).
ReadingRow = tuple[datetime, int, float, int | None]

# Pacing-Callback (live-Modus): wartet bis zum Wall-Clock-Zeitpunkt eines Ticks.
Pacer = Callable[[datetime], Awaitable[None]]


async def copy_readings(session: AsyncSession, records: Sequence[ReadingRow]) -> int:
    """Schreibt einen Reading-Batch über asyncpg-COPY (Research §3.4).

    Der EINZIGE Reading-Schreibweg — genutzt von der Ingestion (F3) und vom
    POST /api/v1/readings-Router (F2). Keine Einzel-Inserts. Gibt die Anzahl
    geschriebener Zeilen zurück; asyncpg-Fehler propagieren (Aufrufer übersetzt).
    """
    if not records:
        return 0
    sa_conn = await session.connection()
    raw = await sa_conn.get_raw_connection()
    asyncpg_conn = raw.driver_connection
    if asyncpg_conn is None:  # pragma: no cover — nur ohne asyncpg-Treiber möglich
        raise RuntimeError("Keine asyncpg-Verbindung für COPY verfügbar")
    await asyncpg_conn.copy_records_to_table(
        "readings", records=list(records), columns=COPY_COLUMNS
    )
    return len(records)


@dataclass
class IngestStats:
    """Zähler des Ingestion-Laufs (für Logs/Tests/Runner-Report)."""

    readings_written: int = 0
    alarms: int = 0
    production_runs: int = 0
    maintenance_events: int = 0
    worker_notes: int = 0
    semantic_events: int = 0
    substrate_refs: int = 0
    notes_embedded: int = 0


@dataclass
class IngestionService:
    """Nimmt den Reading-/Event-Strom eines Adapters auf und persistiert ihn."""

    session: AsyncSession
    pseudonymizer: Pseudonymizer
    redactor: Redactor
    substrate: SubstrateClient | None = None
    # F-SEM: optionaler Embedding-Provider. None → keine Einbettung beim Insert
    # (embedding bleibt NULL; der Backfill holt es nach).
    embedding_provider: EmbeddingProvider | None = None
    batch_size: int = 5000
    _stats: IngestStats = field(default_factory=IngestStats, init=False)
    # Noch nicht committete Notizen dieses Abschnitts — vor dem Commit als EIN
    # Batch eingebettet (F-SEM, best-effort).
    _pending_notes: list[WorkerNote] = field(default_factory=list, init=False)
    # Live-Push (F5): seit dem letzten Commit berührte Maschinen/Datenpunkte/Arten;
    # vor jedem Commit als EIN NOTIFY gebündelt (Vorgabe 4), danach geleert.
    _changed_machines: set[int] = field(default_factory=set, init=False)
    _changed_data_points: set[int] = field(default_factory=set, init=False)
    _changed_kinds: set[str] = field(default_factory=set, init=False)

    async def ingest(self, adapter: SourceAdapter, *, pace: Pacer | None = None) -> IngestStats:
        """Seedet die Topologie, konsumiert den Strom und persistiert alles.

        `pace` (live-Modus) wird bei jedem Tick-Wechsel aufgerufen; davor werden
        die gesammelten Readings committet, damit sie während des Wartens sichtbar
        sind. Im backfill-Modus (`pace=None`) wird nur nach Batch-Größe geflusht.
        """
        self._stats = IngestStats()
        self._pending_notes = []
        self._changed_machines.clear()
        self._changed_data_points.clear()
        self._changed_kinds.clear()
        await adapter.seed_topology(self.session)
        await self.session.flush()  # Topologie-IDs in dieser Transaktion verfügbar

        batch: list[ReadingRow] = []
        last_time: datetime | None = None

        for item in adapter.stream():
            item_time = stream_item_time(item)
            if pace is not None and last_time is not None and item_time != last_time:
                # Tick-Wechsel im live-Modus: Readings sichtbar machen, dann warten.
                await self._flush(batch)
                batch.clear()
                await self._embed_pending_notes()
                await self._emit_change_notification()
                await self.session.commit()
                await pace(item_time)
            last_time = item_time

            if isinstance(item, NormalizedReading):
                batch.append((item.time, item.data_point_id, item.value, item.quality))
                if len(batch) >= self.batch_size:
                    await self._flush(batch)
                    batch.clear()
            else:
                await self._write_event(item)

        await self._flush(batch)
        await self._embed_pending_notes()
        await self._emit_change_notification()
        await self.session.commit()
        logger.info(
            "✅ Ingestion '%s' fertig: %d readings, %d alarms, %d runs, "
            "%d maintenance, %d notes (%d embedded), %d semantic (%d mit substrate_ref).",
            adapter.name,
            self._stats.readings_written,
            self._stats.alarms,
            self._stats.production_runs,
            self._stats.maintenance_events,
            self._stats.worker_notes,
            self._stats.notes_embedded,
            self._stats.semantic_events,
            self._stats.substrate_refs,
        )
        return self._stats

    async def _flush(self, batch: Sequence[ReadingRow]) -> None:
        if not batch:
            return
        self._stats.readings_written += await copy_readings(self.session, batch)
        # Live-Push (F5): berührte Datenpunkte fürs nächste NOTIFY vormerken.
        self._changed_data_points.update(row[1] for row in batch)
        self._changed_kinds.add("reading")

    async def _emit_change_notification(self) -> None:
        """Bündelt die seit dem letzten Commit berührten Entitäten zu EINEM NOTIFY.

        Genau ein pg_notify pro Commit (Vorgabe 4) — der Hub debounct serverseitig
        und lädt danach konsolidiert über den Read-Core nach. Signalisiert nur
        live-relevante Änderungen (Readings → Trend/Status, Alarme → Status/Alarme);
        nicht-live Ereignisse (Wartung, Läufe, Notizen) lösen keinen Push aus.
        """
        await notify_changes(
            self.session,
            ChangeSet(
                machines=frozenset(self._changed_machines),
                data_points=frozenset(self._changed_data_points),
                kinds=frozenset(self._changed_kinds),
            ),
        )
        self._changed_machines.clear()
        self._changed_data_points.clear()
        self._changed_kinds.clear()

    async def _embed_pending_notes(self) -> None:
        """Bettet die gesammelten Notizen vor dem Commit als EINEN Batch ein (best-effort).

        Provider nicht gesetzt / nicht erreichbar → die Notizen bleiben mit
        `embedding=NULL` (der Backfill holt es nach); der Schreibpfad blockiert nie.
        """
        if not self._pending_notes:
            return
        vectors = await embed_best_effort(
            self.embedding_provider, [note.text for note in self._pending_notes]
        )
        if vectors is not None:
            # `strict=False` BEWUSST (anders als der ehrliche Backfill mit strict=True):
            # der Insert-Pfad ist best-effort und darf nie werfen. Der Provider-Vertrag
            # garantiert ohnehin einen Vektor je Text (§15.1) — bliebe wider Erwarten
            # eine Notiz übrig, bleibt sie mit embedding=NULL und der Backfill holt sie.
            for note, vector in zip(self._pending_notes, vectors, strict=False):
                note.embedding = vector
                self._stats.notes_embedded += 1
        self._pending_notes.clear()

    async def _write_event(self, event: NormalizedEvent) -> None:
        if isinstance(event, AlarmEvent):
            await self._write_alarm(event)
        elif isinstance(event, ProductionRunRecord):
            await self._write_production_run(event)
        elif isinstance(event, MaintenanceRecord):
            await self._write_maintenance(event)
        elif isinstance(event, WorkerNoteRecord):
            await self._write_worker_note(event)

    async def _write_alarm(self, event: AlarmEvent) -> None:
        self.session.add(
            Alarm(
                machine_id=event.machine_id,
                component_id=event.component_id,
                data_point_id=event.data_point_id,
                code=event.code,
                message=event.message,
                severity=event.severity,
                category=event.category,
                raised_at=event.occurred_at,
            )
        )
        self._stats.alarms += 1
        # Live-Push (F5): ein Alarm ändert Maschinen-Status (A) + Alarmliste (C).
        self._changed_machines.add(event.machine_id)
        self._changed_kinds.add("alarm")
        await self._mirror(
            machine_id=event.machine_id,
            event_type="alarm_raised",
            payload={
                "code": event.code,
                "severity": event.severity,
                "category": event.category,
                "machine_id": event.machine_id,
                "raised_at": event.occurred_at.isoformat(),
            },
            content=(
                f"Alarm {event.code or '?'} ({event.severity}/{event.category}) "
                f"an Maschine {event.machine_id} ausgelöst."
            ),
        )

    async def _write_production_run(self, event: ProductionRunRecord) -> None:
        self.session.add(
            ProductionRun(
                line_id=event.line_id,
                product_code=event.product_code,
                order_id=event.order_id,
                batch=event.batch,
                started_at=event.started_at,
                ended_at=event.ended_at,
            )
        )
        self._stats.production_runs += 1
        await self._mirror(
            machine_id=None,  # Produktionskontext liegt auf Linien-Ebene
            event_type="production_run",
            payload={
                "product_code": event.product_code,
                "order_id": event.order_id,
                "line_id": event.line_id,
                "started_at": event.started_at.isoformat(),
                "ended_at": event.ended_at.isoformat() if event.ended_at else None,
            },
            content=(
                f"Produktionslauf {event.product_code} auf Linie {event.line_id} "
                f"gestartet ({event.started_at.isoformat()})."
            ),
        )

    async def _write_maintenance(self, event: MaintenanceRecord) -> None:
        performed_by = (
            self.pseudonymizer.tokenize_worker(event.performed_by_ref)
            if event.performed_by_ref
            else None
        )
        self.session.add(
            MaintenanceEvent(
                machine_id=event.machine_id,
                component_id=event.component_id,
                type=event.type,
                description=event.description,
                performed_at=event.occurred_at,
                performed_by=performed_by,  # HMAC-Token, nie Klartext (§8)
            )
        )
        self._stats.maintenance_events += 1
        await self._mirror(
            machine_id=event.machine_id,
            event_type="maintenance_performed",
            payload={
                "type": event.type,
                "machine_id": event.machine_id,
                "component_id": event.component_id,
                "performed_at": event.occurred_at.isoformat(),
                "performed_by": performed_by,  # bereits tokenisiert
            },
            content=(
                f"Wartung ({event.type}) an Maschine {event.machine_id} "
                f"durchgeführt ({event.occurred_at.isoformat()})."
            ),
        )

    async def _write_worker_note(self, event: WorkerNoteRecord) -> None:
        # Datenschutz-Schreibpfad: Freitext NER-maskiert, Autor tokenisiert (§8).
        masked_text = self.redactor.redact_person_names(event.text)
        author = self.pseudonymizer.tokenize_worker(event.author_ref) if event.author_ref else None
        note = WorkerNote(
            machine_id=event.machine_id,
            shift=event.shift,
            text=masked_text,
            author=author,
        )
        # Historische Notiz-Zeit übernehmen (created_at sonst server-default now()).
        note.created_at = event.occurred_at
        self.session.add(note)
        # F-SEM: für das Batch-Embedding vor dem nächsten Commit vormerken (best-effort).
        # Eingebettet wird der NER-maskierte Text (kein Rohtext, §8).
        self._pending_notes.append(note)
        self._stats.worker_notes += 1
        # Werker-Notizen werden NICHT ans Substrat gespiegelt (kein diskretes
        # semantisches Ereignis i. S. v. §9; die semantische Suche läuft über das embedding).

    async def _mirror(
        self, *, machine_id: int | None, event_type: str, payload: dict[str, object], content: str
    ) -> None:
        semantic_event = await record_semantic_event(
            self.session,
            machine_id=machine_id,
            event_type=event_type,
            payload=payload,
            content=content,
            substrate=self.substrate,
        )
        self._stats.semantic_events += 1
        if semantic_event.substrate_ref is not None:
            self._stats.substrate_refs += 1
