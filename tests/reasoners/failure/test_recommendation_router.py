# ============================================================
#  FOREMAN — tests/reasoners/failure/test_recommendation_router.py
#  Zweck: Pflicht-Test-Block der F-REC-Routen (on-demand POST + GET).
#  Prüft: 201 mit deterministischem Sim-Vorbehalt in der Antwort, Auth-Pflicht (401),
#         404 bei fehlender Vorhersage, KEIN Auto-LLM (ohne POST existiert keine
#         Empfehlung → GET 404), Abruf nach Erzeugung. Das LLM-Gateway wird im Test
#         über einen Dependency-Override durch das deterministische Mock-Gateway
#         ersetzt (kein Netz).
#  Architektur-Einordnung: Quality Gate §10.3 (HTTP, echte DB).
# ============================================================
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.api.deps import get_llm_gateway
from foreman.config import Settings
from foreman.db.models import FailurePredictionRecord, Machine
from foreman.llm import LiteLLMGateway

pytestmark = pytest.mark.integration

_BASE = "/api/v1/reasoners/failure"
_REF = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
_TOP_FACTORS: list[dict[str, object]] = [
    {
        "feature": "vibration_rms_velocity_spindle_bearing",
        "value": 3.9,
        "shap": 0.42,
        "direction": "increases_risk",
    },
]


async def _seed_prediction(test_settings: Settings) -> int:
    """Seedet (committed) eine Maschine + FailurePrediction und gibt deren id zurück."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        machine = Machine(label="BAZ-01", machine_class="cnc_machining_center")
        session.add(machine)
        await session.flush()
        record = FailurePredictionRecord(
            machine_id=machine.id,
            reference_time=_REF,
            horizon_h=336,
            probability=0.87,
            decision_threshold=0.5,
            decision="elevated_risk",
            validation_status="simulation_only",
            data_regime="simulation",
            model_version="failure_lgbm@test",
            top_factors=_TOP_FACTORS,
        )
        session.add(record)
        await session.flush()
        prediction_id = record.id
        await session.commit()
    await engine.dispose()
    return prediction_id


def _rec_url(prediction_id: int) -> str:
    return f"{_BASE}/{prediction_id}/recommendation"


def _good_reply(prediction_id: int) -> str:
    return (
        f"Erhöhtes Ausfallrisiko [pred:{prediction_id}]: die steigende Lagervibration "
        f"[factor:vibration_rms_velocity_spindle_bearing] treibt das Risikosignal. "
        f"Empfehlung: das Spindellager bei der nächsten Schicht prüfen. Diese Einschätzung "
        f"beruht auf simulierten Verläufen und ist nicht validiert."
    )


async def test_recommendation_route_liefert_201_mit_vorbehalt(
    app: FastAPI,
    auth_client: AsyncClient,
    test_settings: Settings,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    pred_id = await _seed_prediction(test_settings)
    gateway = make_gateway(backends=[make_backend("local", reply=_good_reply(pred_id))])
    app.dependency_overrides[get_llm_gateway] = lambda: gateway

    resp = await auth_client.post(_rec_url(pred_id))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["validation_status"] == "simulation_only"
    assert body["data_regime"] == "simulation"
    assert body["validation_caveat"]  # deterministisch, nicht leer
    assert body["prediction_id"] == pred_id
    assert f"pred:{pred_id}" in body["referenced_source_ids"]


async def test_recommendation_route_braucht_auth(client: AsyncClient) -> None:
    resp = await client.post(_rec_url(1))
    assert resp.status_code == 401


async def test_recommendation_route_unbekannte_vorhersage_404(
    app: FastAPI,
    auth_client: AsyncClient,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    gateway = make_gateway(backends=[make_backend("local", reply="x")])
    app.dependency_overrides[get_llm_gateway] = lambda: gateway
    resp = await auth_client.post(_rec_url(999_999))
    assert resp.status_code == 404


async def test_get_recommendation_und_kein_auto_llm(
    app: FastAPI,
    auth_client: AsyncClient,
    test_settings: Settings,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    pred_id = await _seed_prediction(test_settings)
    # KEIN Auto-LLM: ohne POST existiert keine Empfehlung → GET 404.
    before = await auth_client.get(_rec_url(pred_id))
    assert before.status_code == 404

    gateway = make_gateway(backends=[make_backend("local", reply=_good_reply(pred_id))])
    app.dependency_overrides[get_llm_gateway] = lambda: gateway
    created = await auth_client.post(_rec_url(pred_id))
    assert created.status_code == 201

    found = await auth_client.get(_rec_url(pred_id))
    assert found.status_code == 200
    assert found.json()["prediction_id"] == pred_id
