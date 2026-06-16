# ============================================================
#  FOREMAN — mcp/tools.py
#  Zweck: Die read-only MCP-Tools (F7) — gemappt auf die MCP-eigene Read-Schicht
#         (reads.py), jeder KI-Output mit dem Transparenz-Wrapper umhüllt, jeder
#         Nicht-KI-Output ehrlich ohne KI-Kennzeichnung. Tools öffnen eine eigene
#         Read-only-Session (kein Commit), messen Latenz/Ergebnis als Metrik und
#         geben PII nur pseudonymisiert/maskiert aus.
#  Architektur-Einordnung: MCP-Schicht (F7). Die Tool-Funktionen tragen die nach
#         außen sichtbare Signatur; Session/Provider werden intern beschafft.
#  Invariante I (Brief §2): read-only — keine Aktorik, kein Reasoner-/LLM-Trigger.
#  Invariante II: jeder KI-stämmige Output trägt seine Transparenz-Flags + Vorbehalt.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from foreman.api.deps import get_embedding_provider
from foreman.db.models import (
    Alarm,
    FailurePredictionRecord,
    FailureRecommendationRecord,
    Machine,
    ReasonerExplanationRecord,
    WorkerNote,
)
from foreman.db.session import get_sessionmaker
from foreman.mcp.schemas import (
    AlarmListOut,
    AlarmOut,
    Confidence,
    DriftStatusOut,
    EventChainListOut,
    EventChainOut,
    FailurePredictionListOut,
    FailurePredictionOut,
    MachineListOut,
    MachineOut,
    NoteHitOut,
    NoteSearchOut,
    PredictionFactor,
    ReadingPoint,
    ReadingsOut,
    RiskDecision,
    WorkerRecommendationOut,
)
from foreman.mcp.transparency import ai_transparency, non_ai_transparency
from foreman.observability.metrics import observe_mcp_call
from foreman.reads import queries as reads
from foreman.reads.status import MachineStatus, compose_status
from foreman.reasoners.failure.schema import ValidationStatus, validation_caveat_for

# Erlaubte Schwere-Stufen für den get_alarms-Filter (eigener, stabiler Außen-Vertrag).
_ALLOWED_SEVERITIES = frozenset({"info", "warning", "alarm", "critical", "emergency"})
# Grenzen gegen Abruf-Last (Brief §5): Trefferzahl Suche, Fenster Trends.
_MAX_SEARCH_K = 50
_DEFAULT_READINGS_HOURS = 24
_MAX_READINGS_HOURS = 168  # 7 Tage


@asynccontextmanager
async def _read_session() -> AsyncIterator[AsyncSession]:
    """Liefert eine Read-only-Session (kein Commit) aus der globalen Session-Factory."""
    maker = get_sessionmaker()
    async with maker() as session:
        # Bewusst KEIN commit — die MCP-Schicht liest ausschließlich (Invariante I).
        yield session


@asynccontextmanager
async def _measured(tool: str) -> AsyncIterator[None]:
    """Misst Latenz + Ergebnis eines Tool-Aufrufs und trägt sie als Metrik ein (§11.2)."""
    started = perf_counter()
    success = False
    try:
        yield
        success = True
    finally:
        observe_mcp_call(tool=tool, latency_seconds=perf_counter() - started, success=success)


# ============================================================
#  Mapping ORM-Datensatz → MCP-Ausgabeschema (rein, testbar)
# ============================================================
def _machine_out(machine: Machine, *, status: MachineStatus, open_alarm_count: int) -> MachineOut:
    return MachineOut(
        id=machine.id,
        line_id=machine.line_id,
        external_id=machine.external_id,
        label=machine.label,
        machine_class=machine.machine_class,
        manufacturer=machine.manufacturer,
        location=machine.location,
        status=status,
        open_alarm_count=open_alarm_count,
        created_at=machine.created_at,
        transparency=non_ai_transparency(),
    )


def _alarm_out(alarm: Alarm) -> AlarmOut:
    return AlarmOut(
        id=alarm.id,
        machine_id=alarm.machine_id,
        component_id=alarm.component_id,
        data_point_id=alarm.data_point_id,
        code=alarm.code,
        message=alarm.message,
        severity=alarm.severity,
        category=alarm.category,
        raised_at=alarm.raised_at,
        cleared_at=alarm.cleared_at,
        acknowledged_at=alarm.acknowledged_at,
        # Pseudonymer Token (HMAC) — unverändert durchgereicht, nie aufgelöst.
        acknowledged_by=alarm.acknowledged_by,
        created_at=alarm.created_at,
        transparency=non_ai_transparency(),
    )


def _prediction_out(record: FailurePredictionRecord) -> FailurePredictionOut:
    # Der Vorbehalts-Satz wird deterministisch abgeleitet (die Vorhersage-Tabelle
    # führt keinen Caveat-Text — nur die Empfehlung tut das).
    caveat = validation_caveat_for(cast(ValidationStatus, record.validation_status))
    factors = [
        PredictionFactor(
            feature=factor["feature"],
            value=factor["value"],
            contribution=factor["shap"],
            direction=factor["direction"],
        )
        for factor in record.top_factors
    ]
    return FailurePredictionOut(
        id=record.id,
        machine_id=record.machine_id,
        reference_time=record.reference_time,
        horizon_h=record.horizon_h,
        probability=record.probability,
        decision_threshold=record.decision_threshold,
        decision=cast(RiskDecision, record.decision),
        top_factors=factors,
        created_at=record.created_at,
        transparency=ai_transparency(
            model_version=record.model_version,
            validation_status=record.validation_status,
            data_regime=record.data_regime,
            validation_caveat=caveat,
        ),
    )


def _recommendation_out(record: FailureRecommendationRecord) -> WorkerRecommendationOut:
    return WorkerRecommendationOut(
        id=record.id,
        prediction_id=record.prediction_id,
        machine_id=record.machine_id,
        recommendation_text=record.recommendation_text,
        referenced_source_ids=list(record.referenced_source_ids),
        horizon_h=record.horizon_h,
        probability=record.probability,
        decision=cast(RiskDecision, record.decision),
        created_at=record.created_at,
        transparency=ai_transparency(
            model_version=record.model_version,
            validation_status=record.validation_status,
            data_regime=record.data_regime,
            # Der gespeicherte, deterministische Vorbehalt (nicht LLM-generiert).
            validation_caveat=record.validation_caveat,
        ),
    )


def _event_chain_out(record: ReasonerExplanationRecord) -> EventChainOut:
    return EventChainOut(
        id=record.id,
        anchor_alarm_id=record.anchor_alarm_id,
        machine_id=record.machine_id,
        narrative=record.narrative,
        referenced_source_ids=list(record.referenced_source_ids),
        flagged_unsupported=list(record.flagged_unsupported),
        is_hypothesis=record.is_hypothesis,
        confidence=cast(Confidence, record.confidence),
        grounded=record.grounded,
        recall_used=record.recall_used,
        created_at=record.created_at,
        # Ereignisketten persistieren keine Modell-Version → ehrlich null (Art. 50(2)).
        transparency=ai_transparency(model_version=None),
    )


def _note_hit_out(note: WorkerNote) -> NoteHitOut:
    return NoteHitOut(
        id=note.id,
        machine_id=note.machine_id,
        shift=note.shift,
        # Bereits NER-maskiert im Schreibpfad; pseudonymer Autor-Token (HMAC).
        text=note.text,
        author=note.author,
        created_at=note.created_at,
        transparency=non_ai_transparency(),
    )


# ============================================================
#  Read-only MCP-Tools (nach außen sichtbare Signaturen)
# ============================================================
async def list_machines() -> MachineListOut:
    """Listet Maschinen-Stammdaten plus aggregierten Status (gesund/Drift/Warnung)."""
    async with _measured("list_machines"), _read_session() as session:
        machines = await reads.list_machines(session)
        open_map = await reads.open_alarms_for_machines(
            session, [machine.id for machine in machines]
        )
        out = [
            _machine_out(machine, status=status, open_alarm_count=count)
            for machine in machines
            for status, count in [compose_status(open_map.get(machine.id, []))]
        ]
        return MachineListOut(machines=out, count=len(out))


async def get_machine(machine_id: int) -> MachineOut:
    """Liefert eine Maschine samt aktuellem Status. Fehler, wenn nicht vorhanden."""
    async with _measured("get_machine"), _read_session() as session:
        machine = await reads.get_machine(session, machine_id)
        if machine is None:
            raise ValueError(f"Maschine {machine_id} nicht gefunden.")
        status, count = compose_status(await reads.open_alarms(session, machine_id))
        return _machine_out(machine, status=status, open_alarm_count=count)


async def get_drift_status(machine_id: int) -> DriftStatusOut:
    """Liefert die aktuelle Drift-Lage einer Maschine (offene, unquittierte Warnungen)."""
    async with _measured("get_drift_status"), _read_session() as session:
        warnings = await reads.list_drift_warnings(session, machine_id=machine_id, only_open=True)
        warn_out = [_alarm_out(alarm) for alarm in warnings]
        return DriftStatusOut(
            machine_id=machine_id,
            drift_active=len(warn_out) > 0,
            open_drift_count=len(warn_out),
            warnings=warn_out,
            transparency=non_ai_transparency(),
        )


async def get_alarms(
    machine_id: int | None = None,
    since: datetime | None = None,
    severity: str | None = None,
) -> AlarmListOut:
    """Liest Alarme (inkl. Drift-Warnungen), optional gefiltert nach Maschine/Zeit/Schwere."""
    # Eingabe vor dem Session-Erwerb prüfen (keine unnötige Ressourcen-Allokation).
    if severity is not None and severity not in _ALLOWED_SEVERITIES:
        raise ValueError(
            f"Unbekannte severity '{severity}'. Erlaubt: {sorted(_ALLOWED_SEVERITIES)}."
        )
    async with _measured("get_alarms"), _read_session() as session:
        alarms = await reads.list_alarms(
            session, machine_id=machine_id, since=since, severity=severity
        )
        out = [_alarm_out(alarm) for alarm in alarms]
        return AlarmListOut(alarms=out, count=len(out))


async def list_failure_predictions(machine_id: int | None = None) -> FailurePredictionListOut:
    """Listet gespeicherte Ausfallvorhersagen — jede trägt ihren Sim-Vorbehalt mit."""
    async with _measured("list_failure_predictions"), _read_session() as session:
        records = await reads.list_predictions(session, machine_id=machine_id)
        out = [_prediction_out(record) for record in records]
        return FailurePredictionListOut(predictions=out, count=len(out))


async def get_failure_prediction(prediction_id: int) -> FailurePredictionOut:
    """Liefert eine gespeicherte Ausfallvorhersage. Fehler, wenn nicht vorhanden."""
    async with _measured("get_failure_prediction"), _read_session() as session:
        record = await reads.get_prediction(session, prediction_id)
        if record is None:
            raise ValueError(f"Vorhersage {prediction_id} nicht gefunden.")
        return _prediction_out(record)


async def get_worker_recommendation(prediction_id: int) -> WorkerRecommendationOut:
    """Liefert die gespeicherte Werker-Empfehlung zu einer Vorhersage (mit Vorbehalt)."""
    async with _measured("get_worker_recommendation"), _read_session() as session:
        record = await reads.get_latest_recommendation(session, prediction_id)
        if record is None:
            raise ValueError(f"Empfehlung zu Vorhersage {prediction_id} nicht gefunden.")
        return _recommendation_out(record)


async def list_event_chains(machine_id: int | None = None) -> EventChainListOut:
    """Listet gespeicherte Ereignisketten-Erklärungen (KI-Output mit Vertrauens-Markern)."""
    async with _measured("list_event_chains"), _read_session() as session:
        records = await reads.list_event_chains(session, machine_id=machine_id)
        out = [_event_chain_out(record) for record in records]
        return EventChainListOut(event_chains=out, count=len(out))


async def get_event_chain(explanation_id: int) -> EventChainOut:
    """Liefert eine gespeicherte Ereignisketten-Erklärung. Fehler, wenn nicht vorhanden."""
    async with _measured("get_event_chain"), _read_session() as session:
        record = await reads.get_event_chain(session, explanation_id)
        if record is None:
            raise ValueError(f"Ereignisketten-Erklärung {explanation_id} nicht gefunden.")
        return _event_chain_out(record)


async def search_notes(query: str, machine_id: int | None = None, k: int = 5) -> NoteSearchOut:
    """Sucht semantisch ähnliche Notizen (Text maskiert, Autor pseudonym, kein LLM)."""
    async with _measured("search_notes"), _read_session() as session:
        bounded_k = max(1, min(k, _MAX_SEARCH_K))
        provider = get_embedding_provider()
        notes = await reads.search_notes(
            provider, session, query, machine_id=machine_id, k=bounded_k
        )
        out = [_note_hit_out(note) for note in notes]
        return NoteSearchOut(hits=out, count=len(out))


async def get_readings(
    machine_id: int, datapoint: str, hours: int = _DEFAULT_READINGS_HOURS
) -> ReadingsOut:
    """Liefert den aggregierten Sensortrend eines Datenpunkts über die letzten `hours`."""
    async with _measured("get_readings"), _read_session() as session:
        bounded_hours = max(1, min(hours, _MAX_READINGS_HOURS))
        data_point = await reads.resolve_data_point(session, machine_id, datapoint)
        if data_point is None:
            raise ValueError(f"Datenpunkt '{datapoint}' an Maschine {machine_id} nicht gefunden.")
        end = datetime.now(UTC)
        start = end - timedelta(hours=bounded_hours)
        points, truncated = await reads.load_readings(session, data_point.id, start, end)
        return ReadingsOut(
            machine_id=machine_id,
            data_point_id=data_point.id,
            data_point_name=data_point.name,
            unit=data_point.unit,
            measurement_type=data_point.measurement_type,
            normal_min=data_point.normal_min,
            normal_max=data_point.normal_max,
            points=[
                ReadingPoint(
                    bucket=point.bucket,
                    avg=point.avg,
                    min=point.min,
                    max=point.max,
                    last=point.last,
                )
                for point in points
            ],
            truncated=truncated,
            transparency=non_ai_transparency(),
        )
