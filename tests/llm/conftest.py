# ============================================================
#  FOREMAN — tests/llm/conftest.py
#  Zweck: Test-Infrastruktur des Modell-Gateways (F-LLM). Ein deterministisches
#         Mock-Backend (KEIN echter LLM-Call) + Fabriken für Backend und Gateway.
#         Damit laufen alle Unit-Tests offline und byte-deterministisch; der
#         einzige echte Round-Trip lebt unter @pytest.mark.smoke (Ollama).
#  Architektur-Einordnung: Quality Gate §10.3. Das Mock-Backend implementiert
#         das Backend-Protokoll — der Gateway sieht keinen Unterschied zu LiteLLM.
# ============================================================
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import pytest

from foreman.llm.backends import Backend, BackendResult
from foreman.llm.cache import ResponseCache
from foreman.llm.errors import BackendUnavailable, GatewayTimeout
from foreman.llm.gateway import LiteLLMGateway
from foreman.llm.rate_limit import RateLimiter


class MockBackend:
    """Deterministisches Mock-Backend für Unit-Tests (kein Netz).

    Modi: feste Antwort (`reply`), Echo der gespotlighteten User-Nachricht
    (`echo`, für die Red-Team-Mechanik), Ausfall (`fail`) oder Timeout
    (`timeout`). Token-Counts sind aus dem Input abgeleitet → reproduzierbar.
    """

    def __init__(
        self,
        name: str = "local",
        *,
        is_local: bool = True,
        reply: str | None = None,
        echo: bool = False,
        fail: bool = False,
        timeout: bool = False,
    ) -> None:
        self.name = name
        self.model = f"mock-{name}"
        self.is_local = is_local
        self._reply = reply
        self._echo = echo
        self._fail = fail
        self._timeout = timeout
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
        if self._timeout:
            raise GatewayTimeout(f"❌ {self.name} Zeitüberschreitung (Mock)")
        if self._fail:
            raise BackendUnavailable(
                f"❌ {self.name} nicht erreichbar (Mock)", attempted=(self.name,)
            )
        if self._echo:
            text = messages[-1]["content"]
        elif self._reply is not None:
            text = self._reply
        else:
            text = f"Antwort von {self.name}"
        return BackendResult(
            text=text,
            model=self.model,
            prompt_tokens=sum(len(m["content"]) for m in messages),
            completion_tokens=len(text.split()),
            finish_reason="stop",
        )


@pytest.fixture
def make_backend() -> Callable[..., MockBackend]:
    """Fabrik für konfigurierte Mock-Backends."""

    def _make(name: str = "local", **kwargs: object) -> MockBackend:
        is_local = bool(kwargs.pop("is_local", name == "local"))
        return MockBackend(name, is_local=is_local, **kwargs)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_gateway() -> Callable[..., LiteLLMGateway]:
    """Fabrik für ein Gateway über Mock-Backends (deterministisch, offline)."""

    def _make(
        *,
        backends: Sequence[Backend] | None = None,
        priority: str = "local_only",
        cache_enabled: bool = False,
        grounding_enabled: bool = True,
        grounding_strict: bool = False,
        rate_capacity: int = 10_000,
        rate_refill: float = 10_000.0,
        now_fn: Callable[[], float] | None = None,
    ) -> LiteLLMGateway:
        resolved = list(backends) if backends is not None else [MockBackend("local")]
        rl = (
            RateLimiter(rate_capacity, rate_refill, now_fn=now_fn)
            if now_fn is not None
            else RateLimiter(rate_capacity, rate_refill)
        )
        return LiteLLMGateway(
            backends=resolved,
            priority=priority,  # type: ignore[arg-type]
            rate_limiter=rl,
            cache=ResponseCache(enabled=cache_enabled),
            grounding_enabled=grounding_enabled,
            grounding_strict=grounding_strict,
            temperature=0.0,
            max_tokens=None,
            timeout_s=30.0,
            local_cost_per_1k=0.0,
            cloud_input_per_1k=0.003,
            cloud_output_per_1k=0.015,
        )

    return _make
