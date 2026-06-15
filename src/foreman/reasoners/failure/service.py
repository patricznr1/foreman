# ============================================================
#  FOREMAN — reasoners/failure/service.py
#  Zweck: Orchestrierung des Ausfallvorhersage-Reasoners (F-PRED). Lädt für eine
#         Maschine + Bezugszeitpunkt die DB-Daten (readings_1m-Reihen, Drift-Output
#         als Feature, Wartung, Alarm-Historie), baut das Vorlauf-Fenster, ruft das
#         geladene Artefakt (predict + SHAP) und persistiert die FailurePrediction.
#  Architektur-Einordnung: Reasoning-Schicht (F-PRED). KEINE Aktorik — der Reasoner
#         empfiehlt, schaltet nichts. On-demand (kein Auto-Predict, §16/§14.3).
#  Sicherheit (§13.3): Die Zahlen (Wahrscheinlichkeit, SHAP) sind autoritativ vom
#         Modell — nie aus einem LLM.
#  STRUKTURELLE EHRLICHKEIT (§16): `validation_status`/`data_regime`/`model_version`
#         stammen aus den Artefakt-Metadaten und werden in JEDE FailurePrediction
#         und jeden persistierten Datensatz durchgereicht — nicht abstreifbar.
# ============================================================
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import (
    Alarm,
    DataPoint,
    FailurePredictionRecord,
    Machine,
    MaintenanceEvent,
    SemanticEvent,
)
from foreman.ingestion.normalized import ensure_utc
from foreman.logging_setup import ERROR, REASON, get_logger
from foreman.observability.metrics import observe_failure_prediction, observe_reasoner_run
from foreman.reasoners.drift.service import DRIFT_ALARM_CODE, DRIFT_EVENT_TYPE
from foreman.reasoners.failure.features import (
    BucketPoint,
    DataPointSeries,
    DriftEvent,
    FeatureWindow,
    extract_features,
)
from foreman.reasoners.failure.model import FailureModel
from foreman.reasoners.failure.schema import FailurePrediction, RiskDecision

logger = get_logger("foreman.reasoners.failure")

REASONER_NAME = "failure"


class MachineNotFoundError(LookupError):
    """Die referenzierte Maschine existiert nicht (→ 404 in der Route)."""

    def __init__(self, machine_id: int) -> None:
        super().__init__(f"Maschine {machine_id} nicht gefunden.")
        self.machine_id = machine_id


def _decision(probability: float, threshold: float) -> RiskDecision:
    """Kostensensitive Entscheidung relativ zum Schwellwert."""
    return "elevated_risk" if probability >= threshold else "normal"


@dataclass
class FailureService:
    """DB-Anbindung des Ausfallvorhersage-Reasoners.

    Reine Logik (Feature-Extraktion, Inferenz, SHAP) liegt in features/model;
    diese Klasse ist die dünne IO-Schale (Session + geladenes Modell). `lookback`
    None → aus den Artefakt-Metadaten (Feature-Verteilungs-Konsistenz).
    """

    session: AsyncSession
    model: FailureModel
    lookback: timedelta | None = None

    async def predict(
        self,
        machine_id: int,
        *,
        reference_time: datetime | None = None,
        lookback: timedelta | None = None,
    ) -> FailurePredictionRecord:
        """Erzeugt on-demand eine Ausfallvorhersage und persistiert sie.

        Wirft `MachineNotFoundError`, wenn die Maschine fehlt.
        """
        t0 = perf_counter()
        try:
            record = await self._run(machine_id, reference_time, lookback)
        except MachineNotFoundError:
            observe_reasoner_run(REASONER_NAME, perf_counter() - t0, success=False)
            raise
        except Exception:
            observe_reasoner_run(REASONER_NAME, perf_counter() - t0, success=False)
            logger.exception("%s Ausfallvorhersage fehlgeschlagen machine_id=%s", ERROR, machine_id)
            raise
        observe_reasoner_run(REASONER_NAME, perf_counter() - t0, success=True)
        return record

    async def _run(
        self,
        machine_id: int,
        reference_time: datetime | None,
        lookback: timedelta | None,
    ) -> FailurePredictionRecord:
        machine = await self.session.get(Machine, machine_id)
        if machine is None:
            raise MachineNotFoundError(machine_id)

        # Auf die Minute floor-en (Konsistenz mit dem readings_1m-Bucket-Raster und
        # dem Trainingspfad): schließt den unfertigen Bucket der laufenden Minute aus
        # (kein Zeit-Leakage über die Bucket-Grenze, §16.2).
        raw_reference = (
            ensure_utc(reference_time) if reference_time is not None else datetime.now(UTC)
        )
        reference = raw_reference.replace(second=0, microsecond=0)
        window_lookback = (
            lookback or self.lookback or timedelta(hours=self.model.metadata.lookback_h)
        )
        window_start = reference - window_lookback

        dp_meta = await self._load_data_point_meta(machine_id)
        window = FeatureWindow(
            reference_time=reference,
            lookback=window_lookback,
            series=tuple(await self._load_series(dp_meta, window_start, reference)),
            drift_events=tuple(await self._load_drift_events(machine_id)),
            maintenance_times=tuple(await self._load_maintenance(machine_id, reference)),
            alarm_times=tuple(await self._load_alarm_times(machine_id, window_start, reference)),
        )
        features = extract_features(window)
        probability, top_factors = self.model.predict(features)
        threshold = self.model.decision_threshold
        meta = self.model.metadata

        prediction = FailurePrediction(
            machine_id=machine_id,
            reference_time=reference,
            horizon_h=self.model.horizon_h,
            probability=probability,
            decision_threshold=threshold,
            decision=_decision(probability, threshold),
            top_factors=tuple(top_factors),
            validation_status=meta.validation_status,
            data_regime=meta.data_regime,
            model_version=meta.model_version,
        )

        record = await self._persist(prediction)
        observe_failure_prediction(
            data_regime=prediction.data_regime,
            decision=prediction.decision,
            probability=prediction.probability,
        )
        # Strukturierter Log (§11.1): autoritative Zahl + Vorbehalt, keine PII.
        logger.info(
            "%s reasoner=failure machine_id=%s probability=%.3f decision=%s "
            "validation_status=%s features=%s",
            REASON,
            machine_id,
            prediction.probability,
            prediction.decision,
            prediction.validation_status,
            len(features),
        )
        return record

    async def _load_data_point_meta(self, machine_id: int) -> dict[int, tuple[str, str | None]]:
        """Datenpunkt-ID → (name, measurement_type) der Maschine."""
        data_points = await self.session.scalars(
            select(DataPoint).where(DataPoint.machine_id == machine_id)
        )
        return {dp.id: (dp.name, dp.measurement_type) for dp in data_points}

    async def _load_series(
        self,
        dp_meta: dict[int, tuple[str, str | None]],
        start: datetime,
        end: datetime,
    ) -> list[DataPointSeries]:
        """Lädt die readings_1m-Reihen je Datenpunkt (avg/min/max) im Vorlauf-Fenster."""
        if not dp_meta:
            return []
        stmt = text(
            "SELECT bucket, data_point_id, avg_value, min_value, max_value "
            "FROM readings_1m "
            "WHERE data_point_id IN :dp_ids AND bucket >= :start AND bucket < :end "
            "ORDER BY bucket"
        ).bindparams(bindparam("dp_ids", expanding=True))
        rows = (
            await self.session.execute(stmt, {"dp_ids": list(dp_meta), "start": start, "end": end})
        ).all()

        points: dict[int, list[BucketPoint]] = defaultdict(list)
        for bucket, data_point_id, avg_value, min_value, max_value in rows:
            if avg_value is None:
                continue
            points[data_point_id].append(
                BucketPoint(
                    bucket=ensure_utc(bucket),
                    avg=avg_value,
                    min=min_value if min_value is not None else avg_value,
                    max=max_value if max_value is not None else avg_value,
                )
            )
        series: list[DataPointSeries] = []
        for data_point_id, (name, measurement_type) in dp_meta.items():
            collected = points.get(data_point_id)
            if collected:
                series.append(
                    DataPointSeries(
                        name=name, measurement_type=measurement_type, points=tuple(collected)
                    )
                )
        return series

    async def _load_drift_events(self, machine_id: int) -> list[DriftEvent]:
        """Drift-Output als Feature: aus den `drift_detected`-semantic_events.

        Der Payload trägt `detected_at` (historische Drift-Zeit, korrekt auch bei
        Backfill) + `effect_size`. Die fensterweise Filterung übernimmt features.py.
        """
        stmt = select(SemanticEvent).where(
            SemanticEvent.machine_id == machine_id,
            SemanticEvent.event_type == DRIFT_EVENT_TYPE,
        )
        events: list[DriftEvent] = []
        for row in await self.session.scalars(stmt):
            payload = row.payload
            detected_at = payload.get("detected_at")
            effect_size = payload.get("effect_size")
            if detected_at is None or effect_size is None:
                continue
            events.append(
                DriftEvent(
                    occurred_at=ensure_utc(datetime.fromisoformat(str(detected_at))),
                    effect_size=float(effect_size),
                )
            )
        return events

    async def _load_maintenance(self, machine_id: int, reference: datetime) -> list[datetime]:
        """Wartungszeitpunkte vor dem Bezugszeitpunkt (kumulativ; »Zeit seit letzter Wartung«)."""
        stmt = select(MaintenanceEvent.performed_at).where(
            MaintenanceEvent.machine_id == machine_id,
            MaintenanceEvent.performed_at < reference,
        )
        return list(await self.session.scalars(stmt))

    async def _load_alarm_times(
        self, machine_id: int, start: datetime, end: datetime
    ) -> list[datetime]:
        """Nicht-Drift-Alarme im Vorlauf-Fenster (Drift fließt über das Drift-Feature)."""
        stmt = select(Alarm.raised_at).where(
            Alarm.machine_id == machine_id,
            Alarm.raised_at >= start,
            Alarm.raised_at < end,
            (Alarm.code != DRIFT_ALARM_CODE) | (Alarm.code.is_(None)),
        )
        return list(await self.session.scalars(stmt))

    async def _persist(self, prediction: FailurePrediction) -> FailurePredictionRecord:
        record = FailurePredictionRecord(
            machine_id=prediction.machine_id,
            reference_time=prediction.reference_time,
            horizon_h=prediction.horizon_h,
            probability=prediction.probability,
            decision_threshold=prediction.decision_threshold,
            decision=prediction.decision,
            validation_status=prediction.validation_status,
            data_regime=prediction.data_regime,
            model_version=prediction.model_version,
            top_factors=[factor.model_dump() for factor in prediction.top_factors],
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record
