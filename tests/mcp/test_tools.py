# ============================================================
#  FOREMAN — tests/mcp/test_tools.py
#  Zweck: Die read-only MCP-Tools festnageln — jedes Tool liefert korrekt aus der
#         Read-Schicht, die Transparenz-Flags sind ehrlich pro Output-Typ, PII
#         erscheint nur pseudonymisiert/maskiert, und KEIN Tool hat Seiteneffekte.
#  Architektur-Einordnung: MCP-Schicht (F7). Integrationstests gegen die Test-DB
#         (skippen sauber, wenn keine DB erreichbar ist).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.core.pseudonymize import Pseudonymizer
from foreman.db.models import (
    Alarm,
    DataPoint,
    FailurePredictionRecord,
    FailureRecommendationRecord,
    Machine,
    Reading,
    ReasonerExplanationRecord,
    WorkerNote,
)
from foreman.mcp import tools
from foreman.reasoners.drift.service import DRIFT_ALARM_CODE

pytestmark = pytest.mark.integration

# Der exakte deterministische Sim-Vorbehalt (DB-CHECK auf failure_recommendations).
_SIM_CAVEAT = (
    "Diese Einschätzung beruht auf simulierten Verläufen und ist nicht an "
    "realen Ausfällen validiert."
)


class _StubProvider:
    """Embedding-Stub: liefert einen festen Query-Vektor (kein echtes Backend)."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1024 for _ in texts]


async def _add_machine(session: AsyncSession, label: str = "Spindel-CNC-01") -> Machine:
    machine = Machine(label=label, external_id="ANON-1", machine_class="cnc")
    session.add(machine)
    await session.flush()
    return machine


async def _add_prediction(
    session: AsyncSession, machine_id: int, *, probability: float = 0.99
) -> FailurePredictionRecord:
    record = FailurePredictionRecord(
        machine_id=machine_id,
        reference_time=datetime.now(UTC),
        horizon_h=336,
        probability=probability,
        decision_threshold=0.5,
        decision="elevated_risk" if probability >= 0.5 else "normal",
        validation_status="simulation_only",
        data_regime="simulation",
        model_version="lgbm-failure-2026.06",
        top_factors=[
            {
                "feature": "vibration_rms__slope",
                "value": 1.2,
                "shap": 0.8,
                "direction": "increases_risk",
            }
        ],
    )
    session.add(record)
    await session.flush()
    return record


# ============================================================
#  Stammdaten + Status
# ============================================================
async def test_list_machines_marks_master_data_as_non_ai(mcp_session: AsyncSession) -> None:
    await _add_machine(mcp_session)
    await mcp_session.commit()

    result = await tools.list_machines()

    assert result.count == 1
    machine = result.machines[0]
    assert machine.label == "Spindel-CNC-01"
    assert machine.status == "healthy"
    # Stammdaten sind KEIN KI-Output.
    assert machine.transparency.ai_generated is False
    assert machine.transparency.generated_by is None


async def test_get_machine_status_drift_active_on_open_drift_alarm(
    mcp_session: AsyncSession,
) -> None:
    machine = await _add_machine(mcp_session)
    mcp_session.add(
        Alarm(
            machine_id=machine.id,
            code=DRIFT_ALARM_CODE,
            severity="warning",
            category="process",
            message="Drift erkannt",
        )
    )
    await mcp_session.commit()

    out = await tools.get_machine(machine.id)

    assert out.status == "drift_active"
    assert out.open_alarm_count == 1


async def test_get_machine_status_open_warning_on_non_drift_alarm(
    mcp_session: AsyncSession,
) -> None:
    machine = await _add_machine(mcp_session)
    mcp_session.add(
        Alarm(machine_id=machine.id, severity="warning", category="hardware", message="Lager heiß")
    )
    await mcp_session.commit()

    out = await tools.get_machine(machine.id)
    assert out.status == "open_warning"


async def test_get_machine_status_healthy_when_alarm_cleared(mcp_session: AsyncSession) -> None:
    machine = await _add_machine(mcp_session)
    mcp_session.add(
        Alarm(
            machine_id=machine.id,
            severity="warning",
            category="process",
            cleared_at=datetime.now(UTC),
        )
    )
    await mcp_session.commit()

    out = await tools.get_machine(machine.id)
    assert out.status == "healthy"


async def test_get_machine_unknown_raises(mcp_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="nicht gefunden"):
        await tools.get_machine(999_999)


# ============================================================
#  Alarme + Drift
# ============================================================
async def test_get_alarms_passes_through_pseudonym_token(
    mcp_session: AsyncSession, pseudonymizer: Pseudonymizer
) -> None:
    machine = await _add_machine(mcp_session)
    token = pseudonymizer.tokenize_worker("1")
    mcp_session.add(
        Alarm(
            machine_id=machine.id,
            severity="warning",
            category="process",
            acknowledged_at=datetime.now(UTC),
            acknowledged_by=token,
        )
    )
    await mcp_session.commit()

    result = await tools.get_alarms(machine_id=machine.id)

    assert result.count == 1
    alarm = result.alarms[0]
    # Nur der HMAC-Token, nie Klartext; unverändert durchgereicht.
    assert alarm.acknowledged_by == token
    assert alarm.transparency.ai_generated is False


async def test_get_alarms_filters_by_since_and_severity(mcp_session: AsyncSession) -> None:
    machine = await _add_machine(mcp_session)
    old = datetime.now(UTC) - timedelta(days=2)
    recent = datetime.now(UTC) - timedelta(minutes=5)
    mcp_session.add(
        Alarm(machine_id=machine.id, severity="info", category="process", raised_at=old)
    )
    mcp_session.add(
        Alarm(machine_id=machine.id, severity="critical", category="hardware", raised_at=recent)
    )
    await mcp_session.commit()

    since = datetime.now(UTC) - timedelta(hours=1)
    result = await tools.get_alarms(machine_id=machine.id, since=since, severity="critical")

    assert result.count == 1
    assert result.alarms[0].severity == "critical"


async def test_get_alarms_invalid_severity_raises(mcp_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="severity"):
        await tools.get_alarms(severity="kaputt")


async def test_get_drift_status_returns_only_open_drift(mcp_session: AsyncSession) -> None:
    machine = await _add_machine(mcp_session)
    mcp_session.add(
        Alarm(machine_id=machine.id, code=DRIFT_ALARM_CODE, severity="warning", category="process")
    )
    # Ein quittierter Drift-Alarm zählt nicht zu "offen".
    mcp_session.add(
        Alarm(
            machine_id=machine.id,
            code=DRIFT_ALARM_CODE,
            severity="warning",
            category="process",
            acknowledged_at=datetime.now(UTC),
        )
    )
    # Ein Nicht-Drift-Alarm ist keine Drift-Warnung.
    mcp_session.add(Alarm(machine_id=machine.id, severity="alarm", category="hardware"))
    await mcp_session.commit()

    out = await tools.get_drift_status(machine.id)

    assert out.drift_active is True
    assert out.open_drift_count == 1
    assert all(w.code == DRIFT_ALARM_CODE for w in out.warnings)
    assert out.transparency.ai_generated is False


# ============================================================
#  Ausfallvorhersage (KI) — trägt den Sim-Vorbehalt
# ============================================================
async def test_list_failure_predictions_carry_validation_flags(mcp_session: AsyncSession) -> None:
    machine = await _add_machine(mcp_session)
    await _add_prediction(mcp_session, machine.id)
    await mcp_session.commit()

    result = await tools.list_failure_predictions(machine_id=machine.id)

    assert result.count == 1
    pred = result.predictions[0]
    assert pred.transparency.ai_generated is True
    assert pred.transparency.generated_by == "foreman-ai"
    assert pred.transparency.requires_human_review is True
    assert pred.transparency.model_version == "lgbm-failure-2026.06"
    assert pred.transparency.validation_status == "simulation_only"
    assert pred.transparency.data_regime == "simulation"
    # Vorhersage trägt den abgeleiteten Vorbehalt mit.
    assert pred.transparency.validation_caveat == _SIM_CAVEAT
    assert pred.top_factors[0].direction == "increases_risk"


async def test_get_failure_prediction_unknown_raises(mcp_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="nicht gefunden"):
        await tools.get_failure_prediction(424_242)


# ============================================================
#  Werker-Empfehlung (KI) — trägt den gespeicherten Vorbehalt
# ============================================================
async def test_get_worker_recommendation_carries_stored_caveat(mcp_session: AsyncSession) -> None:
    machine = await _add_machine(mcp_session)
    pred = await _add_prediction(mcp_session, machine.id)
    mcp_session.add(
        FailureRecommendationRecord(
            prediction_id=pred.id,
            machine_id=machine.id,
            recommendation_text="Lager prüfen.",
            validation_caveat=_SIM_CAVEAT,
            validation_status="simulation_only",
            data_regime="simulation",
            model_version="lgbm-failure-2026.06",
            referenced_source_ids=["pred:1"],
            horizon_h=pred.horizon_h,
            probability=pred.probability,
            decision=pred.decision,
        )
    )
    await mcp_session.commit()

    out = await tools.get_worker_recommendation(pred.id)

    assert out.recommendation_text == "Lager prüfen."
    assert out.transparency.ai_generated is True
    assert out.transparency.validation_caveat == _SIM_CAVEAT
    assert out.transparency.validation_status == "simulation_only"
    # Autoritative Zahl aus der Vorhersage mitgeführt.
    assert out.probability == pytest.approx(pred.probability)


async def test_get_worker_recommendation_unknown_raises(mcp_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="nicht gefunden"):
        await tools.get_worker_recommendation(7_777)


# ============================================================
#  Ereignisketten (KI) — nur event_chain, model_version ehrlich null
# ============================================================
async def _add_explanation(
    session: AsyncSession, machine_id: int, alarm_id: int, *, reasoner: str
) -> ReasonerExplanationRecord:
    record = ReasonerExplanationRecord(
        anchor_alarm_id=alarm_id,
        machine_id=machine_id,
        reasoner=reasoner,
        narrative="Lagerschaden vermutet [alarm:1].",
        referenced_source_ids=["alarm:1"],
        flagged_unsupported=[],
        is_hypothesis=False,
        confidence="medium",
        grounded=True,
        recall_used=False,
    )
    session.add(record)
    await session.flush()
    return record


async def test_list_event_chains_filters_to_event_chain_reasoner(
    mcp_session: AsyncSession,
) -> None:
    machine = await _add_machine(mcp_session)
    alarm = Alarm(machine_id=machine.id, severity="warning", category="process")
    mcp_session.add(alarm)
    await mcp_session.flush()
    await _add_explanation(mcp_session, machine.id, alarm.id, reasoner="event_chain")
    await _add_explanation(mcp_session, machine.id, alarm.id, reasoner="some_other_reasoner")
    await mcp_session.commit()

    result = await tools.list_event_chains(machine_id=machine.id)

    assert result.count == 1
    chain = result.event_chains[0]
    assert chain.transparency.ai_generated is True
    assert chain.transparency.generated_by == "foreman-ai"
    # Ereignisketten persistieren keine Modell-Version → ehrlich null.
    assert chain.transparency.model_version is None


async def test_get_event_chain_rejects_non_event_chain_record(mcp_session: AsyncSession) -> None:
    machine = await _add_machine(mcp_session)
    alarm = Alarm(machine_id=machine.id, severity="warning", category="process")
    mcp_session.add(alarm)
    await mcp_session.flush()
    other = await _add_explanation(
        mcp_session, machine.id, alarm.id, reasoner="some_other_reasoner"
    )
    await mcp_session.commit()

    with pytest.raises(ValueError, match="nicht gefunden"):
        await tools.get_event_chain(other.id)


# ============================================================
#  Semantische Notiz-Suche (Nicht-KI: menschlicher Text, maskiert)
# ============================================================
async def test_search_notes_returns_masked_hit(
    mcp_session: AsyncSession, pseudonymizer: Pseudonymizer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tools, "get_embedding_provider", lambda: _StubProvider())
    machine = await _add_machine(mcp_session)
    author = pseudonymizer.tokenize_worker("7")
    mcp_session.add(
        WorkerNote(
            machine_id=machine.id,
            shift="frueh",
            text="[PERSON] meldet Geräusch am Lager.",
            author=author,
            embedding=[0.1] * 1024,
        )
    )
    await mcp_session.commit()

    result = await tools.search_notes("Geräusch Lager", machine_id=machine.id, k=3)

    assert result.count == 1
    hit = result.hits[0]
    assert hit.author == author  # HMAC-Token, kein Klartext
    assert "[PERSON]" in hit.text
    assert hit.transparency.ai_generated is False  # menschlicher Notiz-Text


# ============================================================
#  Sensortrends (Nicht-KI, aggregiert)
# ============================================================
async def test_get_readings_aggregates_by_data_point_name(mcp_session: AsyncSession) -> None:
    machine = await _add_machine(mcp_session)
    dp = DataPoint(machine_id=machine.id, name="spindle_temperature", kind="analog", unit="°C")
    mcp_session.add(dp)
    await mcp_session.flush()
    base = datetime.now(UTC) - timedelta(minutes=5)
    for offset, value in ((0, 60.0), (60, 61.0), (120, 62.0)):
        mcp_session.add(
            Reading(data_point_id=dp.id, time=base + timedelta(seconds=offset), value=value)
        )
    await mcp_session.commit()

    out = await tools.get_readings(machine.id, "spindle_temperature", hours=1)

    assert out.data_point_name == "spindle_temperature"
    assert out.unit == "°C"
    assert len(out.points) >= 1
    assert out.transparency.ai_generated is False


async def test_get_readings_unknown_data_point_raises(mcp_session: AsyncSession) -> None:
    machine = await _add_machine(mcp_session)
    await mcp_session.commit()
    with pytest.raises(ValueError, match="Datenpunkt"):
        await tools.get_readings(machine.id, "gibt_es_nicht", hours=1)


# ============================================================
#  Read-only — kein Tool schreibt
# ============================================================
async def test_tools_have_no_side_effects(mcp_session: AsyncSession) -> None:
    machine = await _add_machine(mcp_session)
    await _add_prediction(mcp_session, machine.id)
    mcp_session.add(
        Alarm(machine_id=machine.id, code=DRIFT_ALARM_CODE, severity="warning", category="process")
    )
    await mcp_session.commit()

    async def _counts() -> dict[str, int]:
        return {
            "machines": (await mcp_session.scalar(select(func.count()).select_from(Machine))) or 0,
            "alarms": (await mcp_session.scalar(select(func.count()).select_from(Alarm))) or 0,
            "predictions": (
                await mcp_session.scalar(select(func.count()).select_from(FailurePredictionRecord))
            )
            or 0,
        }

    before = await _counts()
    await tools.list_machines()
    await tools.get_machine(machine.id)
    await tools.get_drift_status(machine.id)
    await tools.get_alarms(machine_id=machine.id)
    await tools.list_failure_predictions()
    # Frischer Blick auf die DB (nicht aus dem Identity-Map-Cache der Seed-Session).
    mcp_session.expire_all()
    after = await _counts()

    assert before == after
