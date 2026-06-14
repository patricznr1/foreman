# ============================================================
#  FOREMAN — tests/llm/test_backends_fallback.py
#  Zweck: Pflicht-Test-Block für Backend-Routing + Fallback (F-LLM). Prüft:
#         alle vier Priority-Modi, lokal→Cloud-Fallback, sauberer
#         BackendUnavailable wenn Fallback verboten/erschöpft, LiteLLM→Backend-
#         Mapping, und die Architektur-Grenze: KEINE LiteLLM-Ausnahme dringt
#         durch (Timeout→GatewayTimeout, sonst→BackendUnavailable).
#  Architektur-Einordnung: Quality Gate §10.3. Mock-Backends, kein Netz.
# ============================================================
from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from foreman.llm.backends import (
    Backend,
    BackendResult,
    LiteLLMBackend,
    resolve_chain,
    run_with_fallback,
)
from foreman.llm.errors import BackendUnavailable, GatewayTimeout


class _StubBackend:
    """Mock-Backend für die Fallback-Logik: erfolgreich oder erschöpft."""

    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self.model = f"{name}-model"
        self.is_local = name == "local"
        self._fail = fail
        self.calls = 0

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float,
        max_tokens: int | None,
        timeout_s: float,
    ) -> BackendResult:
        self.calls += 1
        if self._fail:
            raise BackendUnavailable(f"{self.name} nicht erreichbar", attempted=(self.name,))
        return BackendResult(
            text=f"ok von {self.name}",
            model=self.model,
            prompt_tokens=3,
            completion_tokens=2,
            finish_reason="stop",
        )


def test_stub_erfuellt_das_backend_protokoll() -> None:
    assert isinstance(_StubBackend("local"), Backend)


def test_resolve_chain_alle_vier_modi() -> None:
    assert resolve_chain("local_first") == ("local", "cloud")
    assert resolve_chain("cloud_first") == ("cloud", "local")
    assert resolve_chain("local_only") == ("local",)
    assert resolve_chain("cloud_only") == ("cloud",)


async def test_local_first_nutzt_lokal_ohne_fallback() -> None:
    local = _StubBackend("local")
    cloud = _StubBackend("cloud")
    result, used, fallback = await run_with_fallback(
        [local, cloud],
        [{"role": "user", "content": "hi"}],
        temperature=0.0,
        max_tokens=None,
        timeout_s=30.0,
    )
    assert result.text == "ok von local"
    assert used.name == "local"
    assert fallback is False
    assert cloud.calls == 0  # Cloud nie angefasst


async def test_local_first_faellt_auf_cloud_zurueck() -> None:
    local = _StubBackend("local", fail=True)
    cloud = _StubBackend("cloud")
    _result, used, fallback = await run_with_fallback(
        [local, cloud],
        [{"role": "user", "content": "hi"}],
        temperature=0.0,
        max_tokens=None,
        timeout_s=30.0,
    )
    assert used.name == "cloud"
    assert fallback is True
    assert local.calls == 1 and cloud.calls == 1


async def test_cloud_first_versucht_cloud_zuerst() -> None:
    # Kette in Cloud-first-Reihenfolge: erst cloud, dann local.
    cloud = _StubBackend("cloud")
    local = _StubBackend("local")
    _result, used, _fallback = await run_with_fallback(
        [cloud, local],
        [{"role": "user", "content": "hi"}],
        temperature=0.0,
        max_tokens=None,
        timeout_s=30.0,
    )
    assert used.name == "cloud"
    assert local.calls == 0


async def test_local_only_ohne_fallback_wirft_backend_unavailable() -> None:
    local = _StubBackend("local", fail=True)
    with pytest.raises(BackendUnavailable) as exc:
        await run_with_fallback(
            [local],
            [{"role": "user", "content": "hi"}],
            temperature=0.0,
            max_tokens=None,
            timeout_s=30.0,
        )
    assert exc.value.attempted == ("local",)


# --- LiteLLMBackend: Mapping + Fehler-Übersetzung (Architektur-Grenze) ---


class _FakeUsage:
    prompt_tokens = 7
    completion_tokens = 4


class _FakeMessage:
    content = "Antwort vom Modell"


class _FakeChoice:
    message = _FakeMessage()
    finish_reason = "stop"


class _FakeResponse:
    choices = (_FakeChoice(),)
    usage = _FakeUsage()
    model = "ollama/qwen3:14b"


async def test_litellm_backend_mappt_antwort_auf_backend_result() -> None:
    async def fake_fn(**kwargs: object) -> _FakeResponse:
        return _FakeResponse()

    backend = LiteLLMBackend(
        name="local", model="ollama/qwen3:14b", is_local=True, completion_fn=fake_fn
    )
    result = await backend.complete(
        [{"role": "user", "content": "hi"}], temperature=0.0, max_tokens=None, timeout_s=30.0
    )
    assert result.text == "Antwort vom Modell"
    assert result.prompt_tokens == 7
    assert result.completion_tokens == 4
    assert result.finish_reason == "stop"
    assert result.model == "ollama/qwen3:14b"


async def test_litellm_backend_uebersetzt_timeout() -> None:
    async def slow_fn(**kwargs: object) -> object:
        raise TimeoutError("zu lang")

    backend = LiteLLMBackend(name="local", model="m", is_local=True, completion_fn=slow_fn)
    with pytest.raises(GatewayTimeout):
        await backend.complete(
            [{"role": "user", "content": "hi"}], temperature=0.0, max_tokens=None, timeout_s=1.0
        )


async def test_litellm_backend_kapselt_fremde_ausnahme_als_backend_unavailable() -> None:
    # Architektur-Grenze: eine rohe Library-/Provider-Ausnahme darf NIE zum
    # Reasoner durchschlagen — sie wird zu typisiertem BackendUnavailable.
    async def boom_fn(**kwargs: object) -> object:
        raise RuntimeError("provider 500")

    backend = LiteLLMBackend(name="cloud", model="m", is_local=False, completion_fn=boom_fn)
    with pytest.raises(BackendUnavailable):
        await backend.complete(
            [{"role": "user", "content": "hi"}], temperature=0.0, max_tokens=None, timeout_s=1.0
        )


async def test_litellm_backend_erkennt_litellm_timeout_per_name() -> None:
    # Simuliert litellm.Timeout (Klassenname "Timeout") OHNE litellm zu importieren —
    # die namensbasierte Erkennung muss greifen (→ GatewayTimeout, nicht Unavailable).
    class Timeout(Exception):  # noqa: N818 — simuliert bewusst litellms Klassennamen
        pass

    async def fn(**kwargs: object) -> object:
        raise Timeout("provider timeout")

    backend = LiteLLMBackend(name="cloud", model="m", is_local=False, completion_fn=fn)
    with pytest.raises(GatewayTimeout):
        await backend.complete(
            [{"role": "user", "content": "hi"}], temperature=0.0, max_tokens=None, timeout_s=1.0
        )


async def test_litellm_backend_kapselt_malformte_antwort_als_backend_unavailable() -> None:
    # Architektur-Grenze: eine malformte Provider-Antwort (leere choices / message=None)
    # darf NICHT als roher IndexError/AttributeError entkommen — auch das Mapping muss
    # in BackendUnavailable übersetzt werden (sonst durchschlägt es bis zum Reasoner).
    class _EmptyChoices:
        choices: tuple[object, ...] = ()
        usage = _FakeUsage()
        model = "m"

    async def fn(**kwargs: object) -> _EmptyChoices:
        return _EmptyChoices()

    backend = LiteLLMBackend(name="cloud", model="m", is_local=False, completion_fn=fn)
    with pytest.raises(BackendUnavailable):
        await backend.complete(
            [{"role": "user", "content": "hi"}], temperature=0.0, max_tokens=None, timeout_s=1.0
        )
