# ============================================================
#  FOREMAN — tests/integration/test_gateway_error_mapping.py
#  Zweck: Die HTTP-Abbildung der Modell-Gateway-Fehler (§11.2/§13.2). Ein
#         nicht erreichbares Backend und ein erschöpftes Kontingent sind BEKANNTE
#         Betriebszustände — sie müssen als 503/429 erscheinen, nicht als 500.
#         Ohne diese Abbildung sieht eine vorübergehende Einschränkung aus wie
#         ein Absturz.
#  Architektur-Einordnung: Integrationstest gegen die echte App + Test-DB (§10.3).
#  Pflicht-Test-Block: Happy-Path (Fehler kommt an), Edge (Retry-After),
#         Contract (keine Interna in der Antwort), Abgrenzung (Config → 500).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.api.deps import get_llm_gateway
from foreman.config import Settings
from foreman.db.models import Alarm, Machine
from foreman.llm.errors import BackendUnavailable, GatewayTimeout, RateLimited

pytestmark = pytest.mark.integration

_RECONSTRUCT = "/api/v1/reasoners/event_chain/reconstruct"


class _FailingGateway:
    """Gateway-Stub, der bei jedem Aufruf denselben Fehler wirft."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def complete(self, *_args: object, **_kwargs: object) -> object:
        raise self._exc


async def _seed_anchor(test_settings: Settings) -> int:
    """Maschine + Anker-Alarm, damit die Route bis zum Gateway kommt (sonst 404)."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        machine = Machine(label="CNC-1", machine_class="cnc")
        session.add(machine)
        await session.flush()
        anchor = Alarm(
            machine_id=machine.id,
            severity="warning",
            category="process",
            code="DRIFT",
            message="Verhaltens-Drift erkannt",
            raised_at=datetime.now(UTC),
        )
        session.add(anchor)
        await session.flush()
        anchor_id: int = anchor.id
        await session.commit()
    await engine.dispose()
    return anchor_id


@pytest.mark.parametrize(
    "exc",
    [
        BackendUnavailable("kein Backend erreichbar", attempted=("cloud",)),
        GatewayTimeout("Zeitüberschreitung"),
    ],
)
async def test_unavailable_backend_maps_to_503(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings, exc: Exception
) -> None:
    """Backend weg oder zu langsam → 503, nicht 500."""
    anchor_id = await _seed_anchor(test_settings)
    app.dependency_overrides[get_llm_gateway] = lambda: _FailingGateway(exc)

    response = await auth_client.post(_RECONSTRUCT, json={"anchor_alarm_id": anchor_id})

    assert response.status_code == 503, response.text
    assert "vorübergehend nicht verfügbar" in response.json()["detail"]


async def test_503_body_leaks_no_internals(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Contract: die Antwort nennt weder Backend-Namen noch Konfigurationszustände.

    Der Betreiber findet die Details im Log — der Besucher bekommt eine ehrliche,
    aber inhaltsarme Auskunft (§8: keine Interna nach außen)."""
    anchor_id = await _seed_anchor(test_settings)
    app.dependency_overrides[get_llm_gateway] = lambda: _FailingGateway(
        BackendUnavailable(
            "❌ Kein erlaubtes Backend erreichbar (versucht: ['cloud'])", attempted=("cloud",)
        )
    )

    response = await auth_client.post(_RECONSTRUCT, json={"anchor_alarm_id": anchor_id})

    body = response.text.lower()
    assert response.status_code == 503
    for leak in ("cloud", "anthropic", "ollama", "api_key", "versucht"):
        assert leak not in body, f"❌ Interna in der Antwort: {leak}"


async def test_rate_limited_maps_to_429_with_retry_after(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Kontingent erschöpft → 429 mit Retry-After (OWASP LLM10)."""
    anchor_id = await _seed_anchor(test_settings)
    app.dependency_overrides[get_llm_gateway] = lambda: _FailingGateway(
        RateLimited("Rate-Limit erreicht", retry_after_s=2.4)
    )

    response = await auth_client.post(_RECONSTRUCT, json={"anchor_alarm_id": anchor_id})

    assert response.status_code == 429, response.text
    # Aufgerundet und mindestens 1 — ein `Retry-After: 0` wäre eine Einladung zum Hämmern.
    assert response.headers["Retry-After"] == "3"


async def test_retry_after_is_at_least_one_second(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Edge: auch bei retry_after_s=0 steht ein sinnvoller Wert im Header."""
    anchor_id = await _seed_anchor(test_settings)
    app.dependency_overrides[get_llm_gateway] = lambda: _FailingGateway(
        RateLimited("Rate-Limit erreicht", retry_after_s=0.0)
    )

    response = await auth_client.post(_RECONSTRUCT, json={"anchor_alarm_id": anchor_id})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"
