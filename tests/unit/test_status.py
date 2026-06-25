# ============================================================
#  FOREMAN — tests/unit/test_status.py
#  Zweck: Unit-Tests der reinen Status-Komposition (reads/status.compose_status),
#         inkl. der Präzedenz: kritische/Notfall-Severity → `critical` (rot) vor
#         Drift und gewöhnlicher offener Warnung.
#  Konvention (§6): deutsche Kommentare, englische Bezeichner, Type Hints.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime

from foreman.db.models import Alarm
from foreman.reads.status import compose_status
from foreman.reasoners.drift.service import DRIFT_ALARM_CODE


def _alarm(
    severity: str,
    *,
    code: str | None = None,
    acknowledged_at: datetime | None = None,
) -> Alarm:
    """In-Memory-Alarm mit den von compose_status gelesenen Feldern."""
    return Alarm(
        machine_id=1,
        severity=severity,
        category="hardware",
        code=code,
        acknowledged_at=acknowledged_at,
    )


def test_leere_liste_ist_healthy() -> None:
    assert compose_status([]) == ("healthy", 0)


def test_gewoehnlicher_offener_alarm_ist_open_warning() -> None:
    assert compose_status([_alarm("warning")]) == ("open_warning", 1)


def test_unquittierte_drift_ist_drift_active() -> None:
    assert compose_status([_alarm("warning", code=DRIFT_ALARM_CODE)]) == ("drift_active", 1)


def test_quittierte_drift_faellt_auf_open_warning() -> None:
    ack = datetime(2026, 1, 1, tzinfo=UTC)
    result = compose_status([_alarm("warning", code=DRIFT_ALARM_CODE, acknowledged_at=ack)])
    assert result == ("open_warning", 1)


def test_kritische_severity_ist_critical() -> None:
    assert compose_status([_alarm("critical")]) == ("critical", 1)


def test_notfall_severity_ist_critical() -> None:
    assert compose_status([_alarm("emergency")]) == ("critical", 1)


def test_critical_schlaegt_drift() -> None:
    # Offene unquittierte Drift + separater kritischer Alarm → `critical` gewinnt.
    alarms = [_alarm("warning", code=DRIFT_ALARM_CODE), _alarm("critical")]
    assert compose_status(alarms) == ("critical", 2)
