# ============================================================
#  FOREMAN — tests/reasoners/event_chain/conftest.py
#  Zweck: Test-Infrastruktur des Ereignisketten-Reasoners (F6). Ein
#         deterministisches Mock-Backend + Fabrik fürs ECHTE LiteLLMGateway —
#         so laufen Spotlighting + Grounding-Post-Check real durch (kein Netz,
#         kein LLM-Call). Bewusst lokal definiert (keine Kopplung an die
#         F-LLM-conftest), damit die Reasoner-Tests eigenständig sind.
# ============================================================
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import pytest

from foreman.llm.backends import Backend, BackendResult
from foreman.llm.cache import ResponseCache
from foreman.llm.errors import BackendUnavailable
from foreman.llm.gateway import LiteLLMGateway
from foreman.llm.rate_limit import RateLimiter


class MockBackend:
    """Deterministisches Mock-Backend (Backend-Protokoll), kein Netz.

    Modi: feste Antwort (`reply`), Echo der gespotlighteten User-Nachricht (`echo`,
    simuliert ein Modell, das den Freitext 1:1 reflektiert) oder Ausfall (`fail`).
    """

    def __init__(
        self,
        name: str = "local",
        *,
        is_local: bool = True,
        reply: str | None = None,
        echo: bool = False,
        fail: bool = False,
    ) -> None:
        self.name = name
        self.model = f"mock-{name}"
        self.is_local = is_local
        self._reply = reply
        self._echo = echo
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
        return MockBackend(name, **kwargs)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_gateway() -> Callable[..., LiteLLMGateway]:
    """Fabrik fürs ECHTE Gateway über Mock-Backends (deterministisch, offline)."""

    def _make(
        *,
        backends: Sequence[Backend] | None = None,
        grounding_enabled: bool = True,
        grounding_strict: bool = False,
    ) -> LiteLLMGateway:
        resolved = list(backends) if backends is not None else [MockBackend("local")]
        return LiteLLMGateway(
            backends=resolved,
            priority="local_only",  # type: ignore[arg-type]
            rate_limiter=RateLimiter(10_000, 10_000.0),
            cache=ResponseCache(enabled=False),
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
