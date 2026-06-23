# ============================================================
#  FOREMAN — tests/unit/test_dashboard_schemas.py
#  Zweck: Dashboard-Transport-Schemas (F5) — die Read-Core-dataclasses werden
#         JSON-sicher serialisiert (datetimes → ISO), gemeinsam von HTTP-Routen
#         und WebSocket-Push genutzt.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime

from foreman.reads.overview import FleetOverview, MachineOverview
from foreman.reads.queries import ReadingBucket
from foreman.reads.trend import MachineTrend, ProfileBand, ProfileBandPoint
from foreman.schemas.dashboard import FleetOverviewOut, MachineStatusOut, MachineTrendOut


def test_fleet_overview_out_serializes_from_dataclass() -> None:
    overview = FleetOverview(
        machines=(
            MachineOverview(
                id=1,
                label="M1",
                line_id=2,
                machine_class="cnc",
                status="drift_active",
                open_alarm_count=3,
                open_by_severity={"warning": 2, "critical": 1},
                last_alarm_at=datetime(2026, 6, 16, 12, 0, tzinfo=UTC),
            ),
        ),
        by_status={"drift_active": 1},
        open_alarm_total=3,
    )

    payload = FleetOverviewOut.model_validate(overview).model_dump(mode="json")

    assert payload["open_alarm_total"] == 3
    assert payload["by_status"] == {"drift_active": 1}
    entry = payload["machines"][0]
    assert entry["status"] == "drift_active"
    assert entry["open_by_severity"] == {"warning": 2, "critical": 1}
    assert isinstance(entry["last_alarm_at"], str)
    assert entry["last_alarm_at"].startswith("2026-06-16T12:00:00")


def test_machine_status_out_handles_null_last_alarm() -> None:
    entry = MachineOverview(
        id=1,
        label="M1",
        line_id=None,
        machine_class=None,
        status="healthy",
        open_alarm_count=0,
        open_by_severity={},
        last_alarm_at=None,
    )
    payload = MachineStatusOut.model_validate(entry).model_dump(mode="json")
    assert payload["last_alarm_at"] is None
    assert payload["status"] == "healthy"


def test_machine_trend_out_serializes_points_and_reserves_profile_band() -> None:
    trend = MachineTrend(
        machine_id=1,
        data_point_id=2,
        data_point_name="vibration",
        unit="mm/s",
        measurement_type="speed",
        normal_min=0.0,
        normal_max=5.0,
        points=(
            ReadingBucket(
                bucket=datetime(2026, 6, 16, 12, 0, tzinfo=UTC),
                avg=2.5,
                min=2.0,
                max=3.0,
                last=2.5,
            ),
        ),
        truncated=False,
        profile_band=None,
    )

    payload = MachineTrendOut.model_validate(trend).model_dump(mode="json")

    assert payload["normal_min"] == 0.0
    assert payload["normal_max"] == 5.0
    assert payload["points"][0]["avg"] == 2.5
    assert payload["points"][0]["bucket"].startswith("2026-06-16T12:00:00")
    # Ohne persistiertes Profil bleibt das Eigenprofil-Band null (graceful).
    assert payload["profile_band"] is None


def test_machine_trend_out_serializes_profile_band() -> None:
    # Liegt ein Eigenprofil vor, trägt der Vertrag das zeitaufgelöste Band (F4).
    trend = MachineTrend(
        machine_id=1,
        data_point_id=2,
        data_point_name="vibration",
        unit="mm/s",
        measurement_type="speed",
        normal_min=0.0,
        normal_max=5.0,
        points=(
            ReadingBucket(
                bucket=datetime(2026, 6, 16, 8, 0, tzinfo=UTC), avg=2.5, min=2.0, max=3.0, last=2.5
            ),
        ),
        truncated=False,
        profile_band=ProfileBand(
            computed_at=datetime(2026, 6, 16, 22, 0, tzinfo=UTC),
            effect_size_k=3.0,
            points=(
                ProfileBandPoint(
                    bucket=datetime(2026, 6, 16, 8, 0, tzinfo=UTC), lower=1.0, mid=2.5, upper=4.0
                ),
            ),
        ),
    )

    payload = MachineTrendOut.model_validate(trend).model_dump(mode="json")

    band = payload["profile_band"]
    assert band is not None
    assert band["effect_size_k"] == 3.0
    assert band["computed_at"].startswith("2026-06-16T22:00:00")
    assert band["points"][0]["lower"] == 1.0
    assert band["points"][0]["mid"] == 2.5
    assert band["points"][0]["upper"] == 4.0
    assert band["points"][0]["bucket"].startswith("2026-06-16T08:00:00")
