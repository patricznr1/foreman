# ============================================================
#  FOREMAN — schemas/dashboard.py
#  Zweck: Transport-Schemas des Dashboards (F5) — die JSON-Verträge für die
#         HTTP-Read-Routen UND den WebSocket-Push. Validieren direkt aus den
#         Read-Core-dataclasses (from_attributes) und serialisieren JSON-sicher
#         (datetimes → ISO). EINE Wahrheit für beide Transporte.
#  Architektur-Einordnung: API-/WS-Vertrag (Schicht 2). Liest aus dem Read-Core,
#         erfindet keine Felder; der Status-Wertebereich kommt aus reads.status.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from foreman.reads.status import MachineStatus


class _Out(BaseModel):
    """Basis: liest direkt aus Read-Core-dataclasses (from_attributes)."""

    model_config = ConfigDict(from_attributes=True)


class MachineStatusOut(_Out):
    """Aggregierter Maschinen-Status für Statusleiste/Cockpit (Thema machine:{id})."""

    id: int
    label: str
    line_id: int | None
    machine_class: str | None
    status: MachineStatus
    open_alarm_count: int
    open_by_severity: dict[str, int]
    last_alarm_at: datetime | None


class FleetOverviewOut(_Out):
    """Flotten-Lagebild (Thema overview)."""

    machines: list[MachineStatusOut]
    by_status: dict[MachineStatus, int]
    open_alarm_total: int


class TrendPointOut(_Out):
    """Ein aggregierter Minuten-Punkt eines Sensortrends."""

    bucket: datetime
    avg: float
    min: float
    max: float
    last: float | None


class MachineTrendOut(_Out):
    """Aggregierter Sensortrend + statisches Normalband (Thema trend:{data_point_id})."""

    machine_id: int
    data_point_id: int
    data_point_name: str
    unit: str | None
    measurement_type: str | None
    normal_min: float | None
    normal_max: float | None
    points: list[TrendPointOut]
    truncated: bool
    # Reservierter, vorwärtskompatibler Slot für das zustandsspezifische F4-Eigenprofil
    # (entsteht durch gegateten Replay, folgt als eigener Schritt) — bis dahin null.
    profile_band: None = None
