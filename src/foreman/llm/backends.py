# ============================================================
#  FOREMAN — llm/backends.py
#  Zweck: Backend-Auflösung/Routing über LiteLLM (F-LLM) — lokales Backend
#         (Qwen3 über Ollama) + Cloud-Fallback (Anthropic), plus die
#         Prioritäts-/Fallback-Logik. DIES ist die EINZIGE Datei, die LiteLLM
#         importiert (lazy). Kein LiteLLM-Typ verlässt dieses Modul — jede
#         Fremd-Ausnahme wird zu einem typisierten Gateway-Fehler übersetzt
#         (harte Architektur-Grenze des Briefings).
#  Architektur-Einordnung: Schicht 2, hinter der LLMGateway-Abstraktion. Der
#         vLLM-Production-Pfad bleibt durch die Backend-Config offen (nicht
#         jetzt gebaut). Async durchgängig; reine Routing-Funktionen seedbar.
#  Konvention (§6): deutsche Kommentare, keine PII/Keys in Logs.
# ============================================================
from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from foreman.llm.config import Priority
from foreman.llm.errors import BackendUnavailable, GatewayError, GatewayTimeout

# Eine Chat-Nachricht ist ein schlichtes {role, content}-Dict — bewusst KEIN
# LiteLLM-Typ, damit nichts Library-Spezifisches die Abstraktion durchquert.
Message = Mapping[str, str]

# Signatur der Inferenz-Funktion. In Tests injizierbar (kein echter LLM-Call);
# Default lädt LiteLLM lazy. Rückgabe ist die untypisierte LiteLLM-ModelResponse
# (hier bewusst Any, gekapselt — wie river/Presidio in F4).
CompletionFn = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class BackendResult:
    """Normalisiertes Backend-Ergebnis — frei von LiteLLM-Typen."""

    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str


@runtime_checkable
class Backend(Protocol):
    """Ein konkretes Inferenz-Backend (lokal/cloud)."""

    name: str  # "local" | "cloud"
    model: str
    is_local: bool

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        temperature: float,
        max_tokens: int | None,
        timeout_s: float,
    ) -> BackendResult: ...


# Priority-Modus → Reihenfolge der Backend-Namen (GROUND_TRUTH §13).
_CHAINS: dict[str, tuple[str, ...]] = {
    "local_first": ("local", "cloud"),
    "cloud_first": ("cloud", "local"),
    "local_only": ("local",),
    "cloud_only": ("cloud",),
}


def resolve_chain(priority: Priority) -> tuple[str, ...]:
    """Liefert die Backend-Reihenfolge für einen Priority-Modus (rein, seedbar)."""
    return _CHAINS[priority]


async def run_with_fallback(
    chain: Sequence[Backend],
    messages: Sequence[Message],
    *,
    temperature: float,
    max_tokens: int | None,
    timeout_s: float,
    before_attempt: Callable[[str], None] | None = None,
) -> tuple[BackendResult, Backend, bool]:
    """Versucht die Backends in Reihenfolge; fällt bei Nicht-Erreichbarkeit/
    Timeout auf das nächste zurück.

    `before_attempt(name)` wird vor jedem Backend-Versuch aufgerufen (z. B. der
    Rate-Limit-Check). Wirft es (etwa `RateLimited`), propagiert das SOFORT —
    Rate-Limiting ist ein bewusster Stopp, kein Grund für stillen Cloud-Fallback.

    Rückgabe: (Ergebnis, genutztes Backend, fallback_used). Ist die Kette
    erschöpft (oder leer/`*_only` mit verbotenem Fallback), wird ein sauberer
    `BackendUnavailable` mit der Liste der versuchten Backends geworfen.
    """
    attempted: list[str] = []
    last_exc: GatewayError | None = None
    for idx, backend in enumerate(chain):
        attempted.append(backend.name)
        if before_attempt is not None:
            before_attempt(backend.name)
        try:
            result = await backend.complete(
                messages, temperature=temperature, max_tokens=max_tokens, timeout_s=timeout_s
            )
        except (BackendUnavailable, GatewayTimeout) as exc:
            last_exc = exc
            continue
        return result, backend, idx > 0
    raise BackendUnavailable(
        f"❌ Kein erlaubtes Backend erreichbar (versucht: {attempted})", attempted=attempted
    ) from last_exc


async def _default_completion(**kwargs: Any) -> Any:
    """Default-Inferenz: lädt LiteLLM lazy (nur wenn nicht in Tests injiziert)."""
    import litellm

    return await litellm.acompletion(**kwargs)


def _looks_like_timeout(exc: Exception) -> bool:
    """Erkennt LiteLLMs Timeout-Klasse ohne LiteLLM zu importieren (Name-Match)."""
    return type(exc).__name__ in {"Timeout", "APITimeoutError"}


def _extract_result(raw: Any, fallback_model: str) -> BackendResult:
    """Mappt eine LiteLLM-ModelResponse auf BackendResult (Any bewusst gekapselt)."""
    choice = raw.choices[0]
    text = choice.message.content or ""
    finish_reason = getattr(choice, "finish_reason", None) or "stop"
    usage = getattr(raw, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    model = str(getattr(raw, "model", fallback_model) or fallback_model)
    return BackendResult(
        text=str(text),
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        finish_reason=str(finish_reason),
    )


class LiteLLMBackend:
    """Konkretes Backend über LiteLLM. Übersetzt jede Fremd-Ausnahme in einen
    typisierten Gateway-Fehler — nichts LiteLLM-Spezifisches verlässt das Modul."""

    def __init__(
        self,
        *,
        name: str,
        model: str,
        is_local: bool,
        api_key: str | None = None,
        base_url: str | None = None,
        completion_fn: CompletionFn | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.is_local = is_local
        # api_key wird NIE geloggt (§8) — nur an LiteLLM durchgereicht.
        self._api_key = api_key
        self._base_url = base_url
        self._completion_fn = completion_fn or _default_completion

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        temperature: float,
        max_tokens: int | None,
        timeout_s: float,
    ) -> BackendResult:
        call_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [dict(m) for m in messages],
            "temperature": temperature,
            "timeout": timeout_s,
        }
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens
        if self._api_key is not None:
            call_kwargs["api_key"] = self._api_key
        if self._base_url is not None:
            call_kwargs["api_base"] = self._base_url

        try:
            raw = await self._completion_fn(**call_kwargs)
        except TimeoutError as exc:
            raise GatewayTimeout(
                f"❌ Zeitüberschreitung beim Backend '{self.name}' (>{timeout_s}s)"
            ) from exc
        except Exception as exc:
            if _looks_like_timeout(exc):
                raise GatewayTimeout(
                    f"❌ Zeitüberschreitung beim Backend '{self.name}' (>{timeout_s}s)"
                ) from exc
            raise BackendUnavailable(
                f"❌ Backend '{self.name}' nicht erreichbar", attempted=(self.name,)
            ) from exc

        try:
            return _extract_result(raw, self.model)
        except Exception as exc:
            # Architektur-Grenze: auch eine malformte Provider-Antwort (z. B. leere
            # `choices`, `message=None`) darf keine rohe Library-Ausnahme zum
            # Reasoner durchlassen — das Mapping wird ebenfalls gekapselt.
            raise BackendUnavailable(
                f"❌ Backend '{self.name}' lieferte eine unverwertbare Antwort",
                attempted=(self.name,),
            ) from exc
