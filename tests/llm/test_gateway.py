# ============================================================
#  FOREMAN — tests/llm/test_gateway.py
#  Zweck: Pflicht-Test-Block für das Gateway (F-LLM). Teil 1: die Schnittstelle,
#         die jeder kommende Reasoner berührt (Task-Enum, GatewayResponse,
#         LLMGateway-Protokoll). Teil 2 (Orchestrierung: Task-Routing, Response-
#         Struktur, Fehlerfälle) folgt weiter unten gegen das Mock-Backend.
#  Architektur-Einordnung: Quality Gate §10.3. Kein echter LLM-Call.
# ============================================================
from __future__ import annotations

import dataclasses
from collections.abc import Callable

import pytest

from foreman.llm.errors import (
    BackendUnavailable,
    GatewayConfigError,
    GroundingViolation,
    RateLimited,
)
from foreman.llm.gateway import GatewayResponse, LiteLLMGateway, LLMGateway, Task
from foreman.llm.grounding import GroundingReport, GroundingSource


def test_task_enum_hat_die_drei_task_typen() -> None:
    assert {t.value for t in Task} == {"explanation", "synthesis", "classification"}
    # str-Enum: der Wert ist direkt als String nutzbar (Metrik-Label).
    assert Task.EXPLANATION == "explanation"


def test_gateway_response_struktur_und_immutabilitaet() -> None:
    resp = GatewayResponse(
        text="Antwort",
        backend="local",
        model="ollama/qwen3:14b",
        task=Task.EXPLANATION,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        latency_ms=123.4,
        estimated_cost_usd=0.0,
        finish_reason="stop",
    )
    assert resp.text == "Antwort"
    assert resp.total_tokens == 15
    # Defaults der optionalen Felder.
    assert resp.grounding is None
    assert resp.from_cache is False
    assert resp.fallback_used is False
    # GatewayResponse ist immutabel (frozen) — ein gelieferter Response ist Fakt.
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError, ValueError)):
        resp.text = "manipuliert"  # type: ignore[misc]


def test_llm_gateway_ist_runtime_checkable_protocol() -> None:
    class Dummy:
        async def complete(self, **kwargs: object) -> GatewayResponse:
            raise NotImplementedError

    class NotAGateway:
        pass

    assert isinstance(Dummy(), LLMGateway)
    assert not isinstance(NotAGateway(), LLMGateway)


# ============================================================
#  Teil 2 — LiteLLMGateway-Orchestrierung (Mock-Backend, kein Netz)
# ============================================================


async def test_complete_happy_path_liefert_strukturierten_response(
    make_gateway: Callable[..., LiteLLMGateway],
) -> None:
    gateway = make_gateway()
    resp = await gateway.complete(
        task=Task.EXPLANATION,
        system_prompt="Du bist ein Erklär-Layer.",
        user_prompt="Erkläre die Drift an Maschine 7.",
    )
    assert isinstance(resp, GatewayResponse)
    assert resp.text == "Antwort von local"
    assert resp.backend == "local"
    assert resp.task is Task.EXPLANATION
    assert resp.total_tokens == resp.prompt_tokens + resp.completion_tokens
    assert resp.latency_ms >= 0.0
    assert resp.finish_reason == "stop"
    assert resp.from_cache is False
    assert resp.fallback_used is False
    # Lokale Inferenz ist kostenlos.
    assert resp.estimated_cost_usd == 0.0


async def test_complete_routet_task_typ_in_den_response(
    make_gateway: Callable[..., LiteLLMGateway],
) -> None:
    gateway = make_gateway()
    resp = await gateway.complete(task=Task.CLASSIFICATION, system_prompt="s", user_prompt="u")
    assert resp.task is Task.CLASSIFICATION


async def test_complete_haengt_grounding_report_an_wenn_quellen(
    make_gateway: Callable[..., LiteLLMGateway],
) -> None:
    gateway = make_gateway()
    resp = await gateway.complete(
        task=Task.EXPLANATION,
        system_prompt="s",
        user_prompt="Erkläre.",
        sources=[GroundingSource("dp:42", "Temperatur 80 Grad")],
    )
    assert isinstance(resp.grounding, GroundingReport)
    assert resp.grounding.source_ids == ("dp:42",)


async def test_complete_ohne_quellen_hat_keinen_grounding_report(
    make_gateway: Callable[..., LiteLLMGateway],
) -> None:
    gateway = make_gateway()
    resp = await gateway.complete(task=Task.EXPLANATION, system_prompt="s", user_prompt="u")
    assert resp.grounding is None


async def test_complete_strikt_wirft_bei_unbelegter_zahl(
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    # Backend liefert eine fabrizierte 999, die in keiner vertrauenswürdigen
    # Quelle steht → strikter Grounding-Modus reicht GroundingViolation hoch.
    backend = make_backend("local", reply="Die Temperatur lag bei 999 Grad.")
    gateway = make_gateway(backends=[backend], grounding_strict=True)
    with pytest.raises(GroundingViolation):
        await gateway.complete(
            task=Task.EXPLANATION,
            system_prompt="s",
            user_prompt="Erkläre.",
            sources=[GroundingSource("dp:42", "Temperatur 80 Grad")],
        )


async def test_complete_faellt_auf_cloud_zurueck(
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    local = make_backend("local", fail=True)
    cloud = make_backend("cloud", is_local=False, reply="Antwort von cloud")
    gateway = make_gateway(backends=[local, cloud], priority="local_first")
    resp = await gateway.complete(task=Task.SYNTHESIS, system_prompt="s", user_prompt="u")
    assert resp.backend == "cloud"
    assert resp.fallback_used is True
    # Cloud-Kosten > 0 (Token-basierte Schätzung).
    assert resp.estimated_cost_usd > 0.0


async def test_complete_local_only_ohne_fallback_wirft_backend_unavailable(
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    local = make_backend("local", fail=True)
    gateway = make_gateway(backends=[local], priority="local_only")
    with pytest.raises(BackendUnavailable):
        await gateway.complete(task=Task.EXPLANATION, system_prompt="s", user_prompt="u")


async def test_complete_rate_limit_greift(
    make_gateway: Callable[..., LiteLLMGateway],
) -> None:
    # Kapazität 1, kaum Nachfüllung → zweiter Call wird rate-limitiert (LLM10).
    gateway = make_gateway(rate_capacity=1, rate_refill=0.001)
    await gateway.complete(task=Task.EXPLANATION, system_prompt="s", user_prompt="u")
    with pytest.raises(RateLimited):
        await gateway.complete(task=Task.EXPLANATION, system_prompt="s", user_prompt="u")


async def test_complete_grounding_violation_verbucht_cloud_kosten(
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    # Auch ein am strikten Grounding-Gate VERWORFENER Cloud-Call hat real Tokens
    # verbraucht — die Kosten dürfen nicht als 0 verbucht werden (Review-Befund #4).
    from foreman.observability.metrics import GATEWAY_COST

    before: float = GATEWAY_COST.labels(backend="cloud")._value.get()
    backend = make_backend("cloud", is_local=False, echo=True)
    gateway = make_gateway(backends=[backend], priority="cloud_only", grounding_strict=True)
    with pytest.raises(GroundingViolation):
        await gateway.complete(
            task=Task.SYNTHESIS,
            system_prompt="s",
            user_prompt="Erkläre.",
            sources=[
                GroundingSource("dp:42", "Temperatur 80 Grad"),
                GroundingSource("note:1", "999 Grad behauptet", trusted=False),
            ],
        )
    after: float = GATEWAY_COST.labels(backend="cloud")._value.get()
    assert after > before


def test_from_settings_cloud_only_ohne_key_wirft_config_error() -> None:
    from foreman.llm.config import LLMSettings

    settings = LLMSettings(_env_file=None, priority="cloud_only", cloud_api_key=None)
    with pytest.raises(GatewayConfigError):
        LiteLLMGateway.from_settings(settings)


def test_from_settings_baut_gateway_mit_lokalem_backend() -> None:
    from foreman.llm.config import LLMSettings

    settings = LLMSettings(_env_file=None, priority="local_only")
    gateway = LiteLLMGateway.from_settings(settings)
    assert isinstance(gateway, LiteLLMGateway)


# --- Anthropic-Aufruf-Vertrag des Cloud-Pfads (§13.2) ---
#
# Diese beiden Tests prüfen bewusst die ECHTEN LiteLLM-Aufruf-Parameter des echten
# Cloud-Backends. Der Mock-Backend-Pfad der übrigen Gateway-Tests implementiert nur
# das Backend-Protokoll und käme an `call_kwargs` nie vorbei — ein Modell-Wechsel,
# der den Aufruf-Vertrag verletzt, würde dort also unbemerkt durchlaufen.


class _CloudUsage:
    prompt_tokens = 3
    completion_tokens = 2


class _CloudMessage:
    content = "Antwort aus der Cloud"


class _CloudChoice:
    message = _CloudMessage()
    finish_reason = "stop"


class _CloudResponse:
    choices = (_CloudChoice(),)
    usage = _CloudUsage()
    model = "anthropic/claude-sonnet-5"


async def test_cloud_pfad_sendet_keine_sampling_parameter() -> None:
    # Die aktuelle Anthropic-Generation lehnt temperature/top_p/top_k mit HTTP 400
    # ab. Determinismus kommt auf diesem Pfad aus dem Prompt, nicht aus dem Sampling.
    from foreman.llm.config import LLMSettings

    seen: dict[str, object] = {}

    async def capture_fn(**kwargs: object) -> _CloudResponse:
        seen.update(kwargs)
        return _CloudResponse()

    settings = LLMSettings(_env_file=None, priority="cloud_only", cloud_api_key="sk-test")
    gateway = LiteLLMGateway.from_settings(settings, cloud_completion_fn=capture_fn)
    await gateway.complete(task=Task.EXPLANATION, system_prompt="s", user_prompt="u")

    assert "temperature" not in seen
    assert "top_p" not in seen
    assert "top_k" not in seen
    # Das konfigurierte Modell erreicht LiteLLM unverändert.
    assert seen["model"] == settings.cloud_model


async def test_cloud_pfad_schaltet_das_denken_ab() -> None:
    # Denken ist bei diesen Modellen per Default an und teilt sich das Ausgabe-Budget
    # mit dem Antworttext — ohne dieses Abschalten liefe FOREMAN in abgeschnittene
    # Erklärungen (LiteLLM setzt für Anthropic ersatzweise max_tokens=4096).
    from foreman.llm.config import LLMSettings

    seen: dict[str, object] = {}

    async def capture_fn(**kwargs: object) -> _CloudResponse:
        seen.update(kwargs)
        return _CloudResponse()

    settings = LLMSettings(_env_file=None, priority="cloud_only", cloud_api_key="sk-test")
    gateway = LiteLLMGateway.from_settings(settings, cloud_completion_fn=capture_fn)
    await gateway.complete(task=Task.EXPLANATION, system_prompt="s", user_prompt="u")

    assert seen["reasoning_effort"] == "none"
