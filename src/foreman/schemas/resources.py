# ============================================================
#  FOREMAN — schemas/resources.py
#  Zweck: Pydantic-v2 In-(Create) und Out-(Read)-Schemas je CRUD-Ressource.
#  Architektur-Einordnung: API-Vertrag (Schicht 2). Spiegelt das Schema aus
#         GROUND_TRUTH §5; geschlossene Wertebereiche als Literal validiert.
#  Datenschutz: Personen-Felder (`author`/`acknowledged_by`/`performed_by`)
#         nehmen im Input eine user_id an und werden im Schreibpfad zu HMAC-Token;
#         der Output liefert ausschließlich das Token (nie Klartext).
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Geschlossene Wertebereiche (GROUND_TRUTH §5, ohne „…"-Erweiterung).
DataPointKind = Literal["analog", "digital", "setpoint", "counter"]
# `simulation`: synthetische Datenpunkte des Simulations-Adapters (F3). Bewusst
# als eigener Wert geführt, damit Sim-Daten nie als reales Protokoll getarnt
# werden (GROUND_TRUTH §5). Kein DB-CHECK-Constraint vorhanden → keine Migration.
DataPointSource = Literal["opcua", "modbus", "mqtt", "s7", "simulation"]
AlarmSeverity = Literal["info", "warning", "alarm", "critical", "emergency"]


class _ReadBase(BaseModel):
    """Basis aller Out-Schemas: liest direkt aus ORM-Objekten (from_attributes)."""

    model_config = ConfigDict(from_attributes=True)


# --- lines ---
class LineCreate(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)


class LineRead(_ReadBase):
    id: int
    label: str
    location: str | None
    created_at: datetime


# --- machines ---
class MachineCreate(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    line_id: int | None = None
    external_id: str | None = Field(default=None, max_length=255)
    machine_class: str | None = Field(default=None, max_length=128)
    manufacturer: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)


class MachineRead(_ReadBase):
    id: int
    line_id: int | None
    external_id: str | None
    label: str
    machine_class: str | None
    manufacturer: str | None
    location: str | None
    created_at: datetime


# --- components ---
class ComponentCreate(BaseModel):
    machine_id: int
    label: str = Field(min_length=1, max_length=255)
    component_type: str | None = Field(default=None, max_length=64)


class ComponentRead(_ReadBase):
    id: int
    machine_id: int
    label: str
    component_type: str | None
    created_at: datetime


# --- data_points ---
class DataPointCreate(BaseModel):
    machine_id: int
    name: str = Field(min_length=1, max_length=255)
    kind: DataPointKind
    component_id: int | None = None
    measurement_type: str | None = Field(default=None, max_length=32)
    unit: str | None = Field(default=None, max_length=32)
    source: DataPointSource | None = None
    address: str | None = Field(default=None, max_length=255)
    normal_min: float | None = None
    normal_max: float | None = None


class DataPointRead(_ReadBase):
    id: int
    machine_id: int
    component_id: int | None
    name: str
    kind: str
    measurement_type: str | None
    unit: str | None
    source: str | None
    address: str | None
    normal_min: float | None
    normal_max: float | None
    created_at: datetime


# --- alarms ---
class AlarmCreate(BaseModel):
    machine_id: int
    severity: AlarmSeverity
    category: str = Field(min_length=1, max_length=32)
    component_id: int | None = None
    data_point_id: int | None = None
    code: str | None = Field(default=None, max_length=64)
    message: str | None = None
    raised_at: datetime | None = None
    cleared_at: datetime | None = None
    acknowledged_at: datetime | None = None
    # Input: user_id der quittierenden Person → wird zu HMAC-Token tokenisiert.
    acknowledged_by: str | None = Field(default=None, max_length=128)


class AlarmRead(_ReadBase):
    id: int
    machine_id: int
    component_id: int | None
    data_point_id: int | None
    code: str | None
    message: str | None
    severity: str
    category: str
    raised_at: datetime
    cleared_at: datetime | None
    acknowledged_at: datetime | None
    acknowledged_by: str | None  # HMAC-Token, nie Klartext
    created_at: datetime


# --- production_runs ---
class ProductionRunCreate(BaseModel):
    line_id: int
    product_code: str = Field(min_length=1, max_length=128)
    order_id: str | None = Field(default=None, max_length=128)
    batch: str | None = Field(default=None, max_length=128)
    started_at: datetime | None = None
    ended_at: datetime | None = None


class ProductionRunRead(_ReadBase):
    id: int
    line_id: int
    product_code: str
    order_id: str | None
    batch: str | None
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime


# --- maintenance_events ---
class MaintenanceEventCreate(BaseModel):
    machine_id: int
    type: str = Field(min_length=1, max_length=64)
    component_id: int | None = None
    performed_at: datetime | None = None
    description: str | None = None
    # Input: user_id der ausführenden Person → wird zu HMAC-Token tokenisiert.
    performed_by: str | None = Field(default=None, max_length=128)


class MaintenanceEventRead(_ReadBase):
    id: int
    machine_id: int
    component_id: int | None
    type: str
    performed_at: datetime
    description: str | None
    performed_by: str | None  # HMAC-Token, nie Klartext
    created_at: datetime


# --- worker_notes ---
class WorkerNoteCreate(BaseModel):
    text: str = Field(min_length=1)
    machine_id: int | None = None
    shift: str | None = Field(default=None, max_length=16)
    # Input: user_id des Verfassers → wird zu HMAC-Token tokenisiert.
    author: str | None = Field(default=None, max_length=128)


class WorkerNoteRead(_ReadBase):
    id: int
    machine_id: int | None
    shift: str | None
    text: str  # bereits NER-maskiert (Personennamen → [PERSON])
    classification: str | None
    author: str | None  # HMAC-Token, nie Klartext
    created_at: datetime
    # `embedding` wird bewusst NICHT ausgegeben (großer Vektor, in F2 ungenutzt).
