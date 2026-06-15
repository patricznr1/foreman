# ============================================================
#  FOREMAN — reasoners/event_chain/chain.py
#  Zweck: Ketten-Konstruktion als REINER Kern (F6, Baustein 1). Sammelt um ein
#         Anker-Ereignis (Drift-Warnung/Alarm, F4) in einem Zeitfenster die
#         relevanten Ereignisse — vorausgehende Alarme derselben Maschine,
#         Werkernotizen (Auswahl über machine_id + Zeitfenster), Wartungen — und
#         ordnet sie zeitlich. Keine DB, kein Netz: die rohen Kandidaten-Reihen
#         werden injiziert, sodass die Selektions-/Ordnungslogik isoliert testbar
#         ist (§6 DI/Testbarkeit).
#  Architektur-Einordnung: Reasoning-Schicht (F6). Die DB-Anbindung liegt im
#         Service; hier nur reine Funktionen über bereits geladene Reihen.
#  Sicherheit: Werkernotizen werden als `trusted=False` markiert (untrusted
#         Freitext) — die Invariante wandert über ChainEvent.trusted in die
#         Grounding-Quellen.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from foreman.db.models import Alarm, MaintenanceEvent, WorkerNote
from foreman.reasoners.drift.service import DRIFT_ALARM_CODE
from foreman.reasoners.event_chain.schema import (
    ChainEvent,
    ChainEventType,
    ChainWindow,
    EventChain,
)


def _in_window(moment: datetime, window: ChainWindow) -> bool:
    """Ob ein Zeitpunkt im geschlossenen Anker-Fenster [start, end] liegt (beide Grenzen inkl.)."""
    return window.start <= moment <= window.end


def _alarm_summary(alarm: Alarm) -> str:
    """Strukturierte, vertrauenswürdige Zusammenfassung eines Alarms (keine PII)."""
    parts = [f"Alarm (Schwere {alarm.severity}, Kategorie {alarm.category}"]
    if alarm.code:
        parts.append(f", Code {alarm.code}")
    parts.append(")")
    base = "".join(parts)
    if alarm.data_point_id is not None:
        base += f" an Datenpunkt {alarm.data_point_id}"
    if alarm.message:
        base += f": {alarm.message}"
    return base


def _maintenance_summary(event: MaintenanceEvent) -> str:
    """Strukturierte, vertrauenswürdige Zusammenfassung einer Wartung (keine PII)."""
    summary = f"Wartung ({event.type})"
    if event.component_id is not None:
        summary += f" an Komponente {event.component_id}"
    if event.description:
        summary += f": {event.description}"
    return summary


def _anchor_event(anchor: Alarm) -> ChainEvent:
    """Baut das Anker-Ereignis (immer trusted, immer Teil der Kette)."""
    return ChainEvent(
        source_id=f"alarm:{anchor.id}",
        event_type=ChainEventType.ANCHOR_ALARM,
        occurred_at=anchor.raised_at,
        machine_id=anchor.machine_id,
        summary=_alarm_summary(anchor),
        trusted=True,
    )


def _note_event(note: WorkerNote) -> ChainEvent:
    """Baut das (IMMER untrusted) Ketten-Ereignis einer Werkernotiz.

    Sicherheits-Invariante (§14.1/§15): Notiz-Freitext ist `trusted=False` —
    Spotlighting-Quelle, nie Instruktion. Gilt unverändert, egal ob die Notiz
    zeitlich (Zeitfenster) ODER semantisch (Embedding-Suche) ausgewählt wurde.
    """
    return ChainEvent(
        source_id=f"note:{note.id}",
        event_type=ChainEventType.WORKER_NOTE,
        occurred_at=note.created_at,
        machine_id=note.machine_id,
        summary=note.text,
        trusted=False,
    )


def reconstruct_chain(
    *,
    anchor: Alarm,
    window: ChainWindow,
    prior_alarms: Sequence[Alarm] = (),
    worker_notes: Sequence[WorkerNote] = (),
    maintenance_events: Sequence[MaintenanceEvent] = (),
    semantic_notes: Sequence[WorkerNote] = (),
) -> EventChain:
    """Rekonstruiert die zeitlich geordnete Ereigniskette um einen Anker-Alarm.

    Auswahl je Kandidaten-Reihe: identische `machine_id` wie der Anker UND
    Zeitstempel im Fenster. Der Anker selbst ist immer enthalten (auch wenn er am
    Fensterrand liegt). Werkernotizen werden als untrusted (`trusted=False`)
    markiert — ihr Freitext ist die Angriffsfläche und nie eine Instruktion.

    `semantic_notes` (F-SEM, §15): zusätzlich semantisch ähnliche Notizen derselben
    Maschine, die ABSICHTLICH NICHT auf das Zeitfenster beschränkt sind (das ist der
    Sinn der semantischen Auswahl — „hatten wir das schon mal?"). Sie ERGÄNZEN die
    zeitnahen Notizen (Union, dedupliziert über `note.id`); ihre Sicherheits-Behandlung
    ist identisch (untrusted). Default leer → reines F6-Verhalten.

    Reine Funktion: keine DB-/Netz-Zugriffe; die Kandidaten werden injiziert.
    """
    machine_id = anchor.machine_id
    events: list[ChainEvent] = [_anchor_event(anchor)]

    # Vorausgehende/begleitende Alarme derselben Maschine im Fenster (ohne Anker).
    for alarm in prior_alarms:
        if alarm.id == anchor.id or alarm.machine_id != machine_id:
            continue
        if not _in_window(alarm.raised_at, window):
            continue
        event_type = (
            ChainEventType.DRIFT_ALARM
            if alarm.code == DRIFT_ALARM_CODE
            else ChainEventType.PRIOR_ALARM
        )
        events.append(
            ChainEvent(
                source_id=f"alarm:{alarm.id}",
                event_type=event_type,
                occurred_at=alarm.raised_at,
                machine_id=alarm.machine_id,
                summary=_alarm_summary(alarm),
                trusted=True,
            )
        )

    # Werkernotizen (zeitnah): Auswahl über machine_id + Zeitfenster (§5). UNTRUSTED.
    # `seen_note_ids` merkt sich die zeitnahen IDs, damit die semantischen Treffer
    # (unten) nicht doppeln — die DB-Auswahl selbst ist bereits duplikatfrei (PK).
    seen_note_ids: set[int] = set()
    for note in worker_notes:
        if note.machine_id != machine_id or not _in_window(note.created_at, window):
            continue
        seen_note_ids.add(note.id)
        events.append(_note_event(note))

    # F-SEM (§15): semantisch ähnliche Notizen ERGÄNZEN die zeitnahen — gleiche
    # Maschine, aber FENSTER-EXEMPT (relevante Notizen auch außerhalb des engen
    # Fensters). Union, dedupliziert über note.id; UNTRUSTED bleibt unverändert.
    for note in semantic_notes:
        if note.machine_id != machine_id or note.id in seen_note_ids:
            continue
        seen_note_ids.add(note.id)
        events.append(_note_event(note))

    # Wartungsereignisse derselben Maschine im Fenster.
    for maintenance in maintenance_events:
        if maintenance.machine_id != machine_id:
            continue
        if not _in_window(maintenance.performed_at, window):
            continue
        events.append(
            ChainEvent(
                source_id=f"maint:{maintenance.id}",
                event_type=ChainEventType.MAINTENANCE,
                occurred_at=maintenance.performed_at,
                machine_id=maintenance.machine_id,
                summary=_maintenance_summary(maintenance),
                trusted=True,
            )
        )

    # Zeitliche Ordnung; stabiler Tiebreak über die source_id (Determinismus).
    events.sort(key=lambda event: (event.occurred_at, event.source_id))
    return EventChain(
        anchor_alarm_id=anchor.id,
        machine_id=machine_id,
        window=window,
        events=tuple(events),
    )
