# ============================================================
#  FOREMAN — tests/unit/test_normalized.py
#  Zweck: Pflicht-Test-Block für das interne Normalformat (F3).
#  Prüft: tz-aware UTC wird erzwungen (naive → UTC, aware → konvertiert);
#  die diskriminierte Event-Union mappt korrekt auf die konkreten Typen.
#  Architektur-Einordnung: Quality Gate §10.3.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from foreman.ingestion.normalized import (
    AlarmEvent,
    EventKind,
    MaintenanceRecord,
    NormalizedEvent,
    NormalizedReading,
    ProductionRunRecord,
    WorkerNoteRecord,
    ensure_utc,
)

_EVENT_ADAPTER: TypeAdapter[NormalizedEvent] = TypeAdapter(NormalizedEvent)


def test_ensure_utc_naive_wird_als_utc_interpretiert() -> None:
    naive = datetime(2026, 5, 1, 12, 0, 0)
    result = ensure_utc(naive)
    assert result.tzinfo is UTC
    assert result.hour == 12


def test_ensure_utc_aware_wird_konvertiert() -> None:
    plus_two = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    result = ensure_utc(plus_two)
    assert result.utcoffset() == timedelta(0)
    assert result.hour == 10  # 12:00+02:00 → 10:00 UTC


def test_normalized_reading_erzwingt_utc() -> None:
    reading = NormalizedReading(
        time=datetime(2026, 5, 1, 12, tzinfo=timezone(timedelta(hours=2))),
        data_point_id=7,
        value=1.5,
    )
    assert reading.time.tzinfo is UTC
    assert reading.time.hour == 10
    assert reading.quality is None


def test_normalized_reading_ist_frozen() -> None:
    reading = NormalizedReading(time=datetime(2026, 5, 1, tzinfo=UTC), data_point_id=1, value=0.0)
    with pytest.raises(ValidationError):
        reading.value = 2.0  # type: ignore[misc]


def test_event_union_diskriminiert_per_kind() -> None:
    alarm = _EVENT_ADAPTER.validate_python(
        {
            "kind": "alarm",
            "occurred_at": "2026-05-01T09:30:00Z",
            "machine_id": 3,
            "severity": "warning",
            "category": "hardware",
        }
    )
    assert isinstance(alarm, AlarmEvent)
    assert alarm.kind == EventKind.ALARM
    assert alarm.occurred_at.tzinfo is UTC


def test_event_union_production_run_und_maintenance() -> None:
    run = _EVENT_ADAPTER.validate_python(
        {
            "kind": "production_run",
            "occurred_at": "2026-05-01T06:00:00Z",
            "line_id": 1,
            "product_code": "P-100",
            "started_at": "2026-05-01T06:00:00Z",
            "ended_at": "2026-05-01T14:00:00Z",
        }
    )
    assert isinstance(run, ProductionRunRecord)
    assert run.ended_at is not None and run.ended_at.hour == 14

    maintenance = _EVENT_ADAPTER.validate_python(
        {
            "kind": "maintenance",
            "occurred_at": "2026-05-05T10:00:00Z",
            "machine_id": 2,
            "type": "lubrication",
            "performed_by_ref": "U-1",
        }
    )
    assert isinstance(maintenance, MaintenanceRecord)
    assert maintenance.performed_by_ref == "U-1"


def test_worker_note_event_traegt_rohtext_und_autor_ref() -> None:
    note = WorkerNoteRecord(
        occurred_at=datetime(2026, 5, 11, 7, 15, tzinfo=UTC),
        machine_id=2,
        shift="early",
        text="Lager läuft heiß.",
        author_ref="U-2",
    )
    assert note.kind == EventKind.WORKER_NOTE
    assert note.text == "Lager läuft heiß."


def test_event_union_unbekanntes_kind_wird_abgelehnt() -> None:
    with pytest.raises(ValidationError):
        _EVENT_ADAPTER.validate_python(
            {"kind": "explosion", "occurred_at": "2026-05-01T00:00:00Z"}
        )


def test_production_run_occurred_at_gleich_started_at_ist_valide() -> None:
    run = ProductionRunRecord(
        occurred_at=datetime(2026, 5, 1, 8, tzinfo=UTC),
        line_id=1,
        product_code="P-100",
        started_at=datetime(2026, 5, 1, 8, tzinfo=UTC),
    )
    assert run.occurred_at == run.started_at


def test_production_run_occurred_at_ungleich_started_at_wird_abgelehnt() -> None:
    # occurred_at trägt die Strom-Sortierung, started_at den fachlichen Laufstart.
    # Driften sie auseinander, wird die Zeitachse widersprüchlich → hart ablehnen.
    with pytest.raises(ValidationError):
        ProductionRunRecord(
            occurred_at=datetime(2026, 5, 1, 8, tzinfo=UTC),
            line_id=1,
            product_code="P-100",
            started_at=datetime(2026, 5, 1, 9, tzinfo=UTC),
        )
