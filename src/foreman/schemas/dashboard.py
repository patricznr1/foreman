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


class StreamStatusOut(_Out):
    """Zustand des Eingangs-Live-Streams (Zwilling als Datenquelle, §12.6/§22.2).

    `active=True` = der Live-Worker tickt fortlaufend frische Wall-Clock-Readings;
    `last_reading_at` ist der jüngste Reading-Stempel der Simulationsquelle (Stand)
    oder null. Speist das globale „Live"-Badge ehrlich (kein Live-Etikett über
    statischer Historie).
    """

    active: bool
    last_reading_at: datetime | None


class FleetOverviewOut(_Out):
    """Flotten-Lagebild (Thema overview)."""

    machines: list[MachineStatusOut]
    by_status: dict[MachineStatus, int]
    open_alarm_total: int
    stream: StreamStatusOut


class TrendPointOut(_Out):
    """Ein aggregierter Minuten-Punkt eines Sensortrends."""

    bucket: datetime
    avg: float
    min: float
    max: float
    last: float | None


class ProfileBandPointOut(_Out):
    """Ein zeitaufgelöster Korridorpunkt des Eigenprofil-Bands (F4)."""

    bucket: datetime
    lower: float
    mid: float
    upper: float


class ProfileBandOut(_Out):
    """Das zustandsspezifische Eigenprofil-Band (F4) entlang der Trend-Buckets.

    `mid` = gleitender Zustands-Median, `lower`/`upper` = Korridor
    `median +/- effect_size_k * noise_sigma` (echte Detektor-Bewertungsbasis).
    `computed_at` = Profil-Stand (kein Live-Wert).
    """

    computed_at: datetime
    effect_size_k: float
    points: list[ProfileBandPointOut]


class MachineTrendOut(_Out):
    """Aggregierter Sensortrend + statisches Normalband + F4-Eigenprofil-Band."""

    machine_id: int
    data_point_id: int
    data_point_name: str
    unit: str | None
    measurement_type: str | None
    normal_min: float | None
    normal_max: float | None
    points: list[TrendPointOut]
    truncated: bool
    # Zustandsspezifisches F4-Eigenprofil-Band (gegateter Replay, persistiert in
    # drift_profiles); null, wenn kein/zu junges Profil vorliegt (graceful).
    profile_band: ProfileBandOut | None = None
