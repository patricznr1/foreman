# ============================================================
#  FOREMAN — tests/reasoners/event_chain/test_chain.py
#  Zweck: Reiner Kern (F6, Baustein 1) — Sammlung, Zeitfenster, machine_id-Match,
#         temporale Ordnung, trusted-Markierung. Ohne DB/Netz: ORM-Objekte werden
#         in-memory konstruiert (Zeitstempel/IDs explizit gesetzt).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from foreman.db.models import Alarm, MaintenanceEvent, WorkerNote
from foreman.reasoners.event_chain.chain import reconstruct_chain
from foreman.reasoners.event_chain.schema import ChainEventType, ChainWindow

_ANCHOR_TIME = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)


def _window(days: int = 7) -> ChainWindow:
    return ChainWindow(start=_ANCHOR_TIME - timedelta(days=days), end=_ANCHOR_TIME)


def _anchor(machine_id: int = 1, code: str | None = "DRIFT") -> Alarm:
    return Alarm(
        id=100,
        machine_id=machine_id,
        severity="warning",
        category="process",
        code=code,
        message="Verhaltens-Drift erkannt",
        data_point_id=7,
        raised_at=_ANCHOR_TIME,
    )


def _note(note_id: int, machine_id: int | None, *, hours_before: float, text: str = "Lager läuft heiß") -> WorkerNote:
    return WorkerNote(
        id=note_id,
        machine_id=machine_id,
        shift="frueh",
        text=text,
        created_at=_ANCHOR_TIME - timedelta(hours=hours_before),
    )


def test_reconstruct_chain_nur_anker_liefert_ein_ereignis() -> None:
    chain = reconstruct_chain(anchor=_anchor(), window=_window())
    assert len(chain.events) == 1
    anchor_event = chain.events[0]
    assert anchor_event.event_type is ChainEventType.ANCHOR_ALARM
    assert anchor_event.source_id == "alarm:100"
    assert anchor_event.trusted is True
    assert chain.anchor_alarm_id == 100
    assert chain.machine_id == 1


def test_reconstruct_chain_andere_maschine_wird_ausgeschlossen() -> None:
    note_same = _note(1, machine_id=1, hours_before=2)
    note_other = _note(2, machine_id=99, hours_before=2)
    chain = reconstruct_chain(
        anchor=_anchor(), window=_window(), worker_notes=[note_same, note_other]
    )
    source_ids = {event.source_id for event in chain.events}
    assert "note:1" in source_ids
    assert "note:2" not in source_ids


def test_reconstruct_chain_ausserhalb_des_fensters_wird_ausgeschlossen() -> None:
    inside = _note(1, machine_id=1, hours_before=10)
    before = _note(2, machine_id=1, hours_before=24 * 30)  # 30 Tage vor Anker
    after = WorkerNote(
        id=3,
        machine_id=1,
        text="nach dem Anker",
        created_at=_ANCHOR_TIME + timedelta(hours=1),
    )
    chain = reconstruct_chain(
        anchor=_anchor(), window=_window(), worker_notes=[inside, before, after]
    )
    source_ids = {event.source_id for event in chain.events}
    assert source_ids == {"alarm:100", "note:1"}


def test_reconstruct_chain_temporale_ordnung() -> None:
    note_early = _note(1, machine_id=1, hours_before=48)
    note_late = _note(2, machine_id=1, hours_before=2)
    chain = reconstruct_chain(
        anchor=_anchor(), window=_window(), worker_notes=[note_late, note_early]
    )
    times = [event.occurred_at for event in chain.events]
    assert times == sorted(times)
    # Anker ist das jüngste Ereignis (Fenster-Ende) → steht zuletzt.
    assert chain.events[-1].source_id == "alarm:100"


def test_reconstruct_chain_worker_note_ist_untrusted() -> None:
    chain = reconstruct_chain(
        anchor=_anchor(), window=_window(), worker_notes=[_note(1, 1, hours_before=3)]
    )
    note_event = next(e for e in chain.events if e.source_id == "note:1")
    assert note_event.trusted is False
    assert note_event.event_type is ChainEventType.WORKER_NOTE


def test_reconstruct_chain_drift_vs_prior_alarm_typisierung() -> None:
    drift = Alarm(
        id=200, machine_id=1, severity="warning", category="process",
        code="DRIFT", raised_at=_ANCHOR_TIME - timedelta(hours=12),
    )
    other = Alarm(
        id=201, machine_id=1, severity="alarm", category="hardware",
        code="OVERTEMP", raised_at=_ANCHOR_TIME - timedelta(hours=6),
    )
    chain = reconstruct_chain(
        anchor=_anchor(), window=_window(), prior_alarms=[drift, other]
    )
    by_id = {e.source_id: e for e in chain.events}
    assert by_id["alarm:200"].event_type is ChainEventType.DRIFT_ALARM
    assert by_id["alarm:201"].event_type is ChainEventType.PRIOR_ALARM
    assert by_id["alarm:200"].trusted is True


def test_reconstruct_chain_anker_nicht_doppelt() -> None:
    # Anker taucht (versehentlich) auch in prior_alarms auf → darf nicht doppelt rein.
    chain = reconstruct_chain(
        anchor=_anchor(), window=_window(), prior_alarms=[_anchor()]
    )
    assert sum(1 for e in chain.events if e.source_id == "alarm:100") == 1


def test_reconstruct_chain_wartung_im_fenster_ist_trusted() -> None:
    maintenance = MaintenanceEvent(
        id=5, machine_id=1, component_id=3, type="lubrication",
        description="Spindel nachgeschmiert",
        performed_at=_ANCHOR_TIME - timedelta(hours=20),
    )
    chain = reconstruct_chain(
        anchor=_anchor(), window=_window(), maintenance_events=[maintenance]
    )
    maint_event = next(e for e in chain.events if e.source_id == "maint:5")
    assert maint_event.event_type is ChainEventType.MAINTENANCE
    assert maint_event.trusted is True
    assert "lubrication" in maint_event.summary
