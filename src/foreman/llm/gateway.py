# ============================================================
#  FOREMAN — llm/gateway.py
#  Zweck: Die LLMGateway-Abstraktion (F-LLM) — die EINZIGE Schnittstelle, die
#         ein Reasoner je berührt: das Task-Enum, der strukturierte
#         GatewayResponse, das LLMGateway-Protokoll und (weiter unten) die
#         konkrete LiteLLMGateway-Implementierung. Kein reasoner-fähiger Pfad
#         exponiert LiteLLM-Typen (harte Architektur-Grenze des Briefings).
#  Architektur-Einordnung: Schicht 2 — die Abstraktion, auf der jeder kommende
#         LLM-Reasoner (zuerst Ereignisketten) aufsetzt. Async durchgängig.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from time import perf_counter
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from foreman.llm.backends import (
    Backend,
    CompletionFn,
    LiteLLMBackend,
    resolve_chain,
    run_with_fallback,
)
from foreman.llm.cache import ResponseCache
from foreman.llm.config import LLMSettings, Priority
from foreman.llm.errors import GatewayConfigError, GatewayError
from foreman.llm.grounding import (
    GroundingReport,
    GroundingSource,
    build_spotlighted_messages,
    check_grounding,
)
from foreman.llm.rate_limit import RateLimiter
from foreman.logging_setup import REASON, get_logger
from foreman.observability.metrics import observe_gateway_call, record_gateway_cache_hit

logger = get_logger("foreman.llm.gateway")


class Task(StrEnum):
    """Task-Typ eines Gateway-Aufrufs — steuert Routing/Defaults und Metrik-Labels.

    StrEnum: der Wert ist direkt als niedrig-kardinales Metrik-Label nutzbar.
    """

    EXPLANATION = "explanation"  # natürlichsprachliche Erklärung über Fakten
    SYNTHESIS = "synthesis"  # Zusammenführung (z. B. Ereignisketten-Erzählung)
    CLASSIFICATION = "classification"  # Einordnung/Kategorisierung


class GatewayResponse(BaseModel):
    """Strukturierte, immutable Antwort des Gateways.

    Bündelt alles, was ein Reasoner über einen Aufruf wissen muss — ohne je ein
    LiteLLM-Konzept zu sehen: Text, genutztes Backend/Modell, Token-Counts,
    Latenz, geschätzte Kosten, Grounding-Report, Finish-Reason plus die
    Mechanik-Flags (Cache-Treffer, Fallback genutzt).
    """

    model_config = {"frozen": True}

    text: str
    backend: str  # "local" | "cloud"
    model: str  # konkretes Modell-Id, das geantwortet hat
    task: Task
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_cost_usd: float
    finish_reason: str
    grounding: GroundingReport | None = None
    from_cache: bool = False
    fallback_used: bool = False


@runtime_checkable
class LLMGateway(Protocol):
    """Das Protokoll, das Reasoner konsumieren — die gesamte LLM-Oberfläche.

    Ein Reasoner übergibt System-Prompt, die eigentliche Anfrage und optional die
    Grounding-Quellen (vertrauenswürdige Reasoner-/DB-Daten + untrusted
    Werker-Freitext). Das Gateway baut daraus den gespotlighteten Prompt, routet
    task-typisiert an ein Backend, prüft das Grounding und liefert eine
    `GatewayResponse`. Keine LiteLLM-Typen in der Signatur.
    """

    async def complete(
        self,
        *,
        task: Task,
        system_prompt: str,
        user_prompt: str,
        sources: Sequence[GroundingSource] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GatewayResponse: ...


class LiteLLMGateway:
    """Konkrete LLMGateway-Implementierung über LiteLLM-Backends.

    Orchestriert pro `complete()`: Cache-Check → Prompt-Bau (Spotlighting) →
    Rate-Limit + Backend-Routing/Fallback → Grounding-Post-Check → Metriken +
    strukturierter Log. LiteLLM bleibt vollständig in `backends.py` gekapselt —
    diese Klasse (und alles, was ein Reasoner sieht) kennt nur FOREMAN-Typen.
    """

    def __init__(
        self,
        *,
        backends: Sequence[Backend],
        priority: Priority,
        rate_limiter: RateLimiter,
        cache: ResponseCache,
        grounding_enabled: bool,
        grounding_strict: bool,
        temperature: float,
        max_tokens: int | None,
        timeout_s: float,
        local_cost_per_1k: float,
        cloud_input_per_1k: float,
        cloud_output_per_1k: float,
    ) -> None:
        self._backends: dict[str, Backend] = {b.name: b for b in backends}
        self._priority = priority
        self._rate_limiter = rate_limiter
        self._cache = cache
        self._grounding_enabled = grounding_enabled
        self._grounding_strict = grounding_strict
        self._default_temperature = temperature
        self._default_max_tokens = max_tokens
        self._timeout_s = timeout_s
        self._local_cost_per_1k = local_cost_per_1k
        self._cloud_input_per_1k = cloud_input_per_1k
        self._cloud_output_per_1k = cloud_output_per_1k

    @classmethod
    def from_settings(
        cls,
        settings: LLMSettings,
        *,
        local_completion_fn: CompletionFn | None = None,
        cloud_completion_fn: CompletionFn | None = None,
    ) -> LiteLLMGateway:
        """Baut das Gateway aus der LLM-Config. Wirft `GatewayConfigError`, wenn
        ein nötiges Backend nicht konfiguriert ist (z. B. cloud_only ohne Key).

        Die `*_completion_fn`-Injektionspunkte erlauben deterministische Tests
        ohne echten LiteLLM-Call (Default lädt LiteLLM lazy)."""
        needed = set(resolve_chain(settings.priority))
        backends: list[Backend] = []
        if "local" in needed:
            backends.append(
                LiteLLMBackend(
                    name="local",
                    model=settings.local_model,
                    is_local=True,
                    base_url=settings.local_base_url,
                    completion_fn=local_completion_fn,
                )
            )
        if "cloud" in needed:
            api_key = (
                settings.cloud_api_key.get_secret_value()
                if settings.cloud_api_key is not None
                else None
            )
            # Nur cloud_only ohne Key ist ein Bau-Fehler (Cloud ist dort das EINZIGE
            # Backend). Bei cloud_first/local_first ohne Key bleibt das Cloud-Backend
            # bewusst zugelassen — ein fehlender Key macht es zur Laufzeit nur
            # unerreichbar, der lokale Pfad trägt (lokal-first-Philosophie).
            if settings.priority == "cloud_only" and api_key is None:
                raise GatewayConfigError(
                    "❌ priority=cloud_only, aber FOREMAN_LLM_CLOUD_API_KEY fehlt."
                )
            backends.append(
                LiteLLMBackend(
                    name="cloud",
                    model=settings.cloud_model,
                    is_local=False,
                    api_key=api_key,
                    completion_fn=cloud_completion_fn,
                )
            )
        return cls(
            backends=backends,
            priority=settings.priority,
            rate_limiter=RateLimiter(
                settings.rate_limit_capacity, settings.rate_limit_refill_per_s
            ),
            cache=ResponseCache(enabled=settings.cache_enabled),
            grounding_enabled=settings.grounding_enabled,
            grounding_strict=settings.grounding_strict,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout_s=settings.request_timeout_s,
            local_cost_per_1k=settings.local_cost_per_1k_tokens,
            cloud_input_per_1k=settings.cloud_input_cost_per_1k,
            cloud_output_per_1k=settings.cloud_output_cost_per_1k,
        )

    def _build_messages(
        self, system_prompt: str, user_prompt: str, sources: Sequence[GroundingSource]
    ) -> list[dict[str, str]]:
        """Baut die Nachrichten: mit Grounding den gespotlighteten Prompt (Daten-
        block + datamarkierter Freitext), die eigentliche Anfrage vorangestellt."""
        if self._grounding_enabled and sources:
            grounded = build_spotlighted_messages(system_prompt, sources)
            return [
                grounded[0],
                {"role": "user", "content": f"{user_prompt}\n\n{grounded[1]['content']}"},
            ]
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _cost_for(self, backend: Backend, prompt_tokens: int, completion_tokens: int) -> float:
        """Schätzt die Kosten aus Token-Counts pro Backend (lokal i. d. R. 0)."""
        if backend.is_local:
            return (prompt_tokens + completion_tokens) / 1000.0 * self._local_cost_per_1k
        return (
            prompt_tokens / 1000.0 * self._cloud_input_per_1k
            + completion_tokens / 1000.0 * self._cloud_output_per_1k
        )

    async def complete(
        self,
        *,
        task: Task,
        system_prompt: str,
        user_prompt: str,
        sources: Sequence[GroundingSource] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GatewayResponse:
        srcs: tuple[GroundingSource, ...] = tuple(sources or ())
        temp = temperature if temperature is not None else self._default_temperature
        maxt = max_tokens if max_tokens is not None else self._default_max_tokens

        chain_names = resolve_chain(self._priority)
        chain = [self._backends[n] for n in chain_names if n in self._backends]
        if not chain:
            raise GatewayConfigError(f"❌ Kein Backend für priority={self._priority} konfiguriert.")

        # Cache-Key über die LOGISCHEN Eingaben (nicht den Zufalls-Delimiter).
        # `model` = PRIMÄR-Backend-Modell (chain[0]) als stabiler Stellvertreter:
        # bewusst deterministisch je Gateway-Config; eine per Fallback erzeugte
        # Antwort wird daher unter dem Primärmodell-Key gecacht (akzeptierter
        # Trade-off — der Response benennt Backend/Modell/fallback_used selbst, §13.4).
        cache_key = ResponseCache.make_key(
            model=chain[0].model,
            task=task,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            sources=srcs,
            temperature=temp,
            max_tokens=maxt,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            record_gateway_cache_hit()
            return cached

        messages = self._build_messages(system_prompt, user_prompt, srcs)

        t0 = perf_counter()
        try:
            result, used, fallback_used = await run_with_fallback(
                chain,
                messages,
                temperature=temp,
                max_tokens=maxt,
                timeout_s=self._timeout_s,
                before_attempt=self._rate_limiter.check,
            )
        except GatewayError:
            # Rate-Limit/Backend-Ausfall/Timeout — als Fehler zählen, dann hoch.
            observe_gateway_call(
                backend=chain[0].name,
                task=task.value,
                latency_seconds=perf_counter() - t0,
                success=False,
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0.0,
                fallback_used=False,
            )
            raise

        latency_ms = (perf_counter() - t0) * 1000.0
        # Kosten VOR dem Grounding-Check bestimmen: der Backend-Call ist bereits
        # erfolgt und hat (ggf. Cloud-)Kosten verursacht — auch ein am Grounding-Gate
        # verworfener Output muss korrekt verbucht werden (Konsistenz mit den Tokens).
        cost = self._cost_for(used, result.prompt_tokens, result.completion_tokens)

        # Grounding-Post-Check (strikt → GroundingViolation; sonst Report).
        grounding_report: GroundingReport | None = None
        if self._grounding_enabled and srcs:
            try:
                grounding_report = check_grounding(result.text, srcs, strict=self._grounding_strict)
            except GatewayError:
                observe_gateway_call(
                    backend=used.name,
                    task=task.value,
                    latency_seconds=latency_ms / 1000.0,
                    success=False,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    cost_usd=cost,
                    fallback_used=fallback_used,
                )
                raise

        response = GatewayResponse(
            text=result.text,
            backend=used.name,
            model=result.model,
            task=task,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.prompt_tokens + result.completion_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=cost,
            finish_reason=result.finish_reason,
            grounding=grounding_report,
            from_cache=False,
            fallback_used=fallback_used,
        )
        observe_gateway_call(
            backend=used.name,
            task=task.value,
            latency_seconds=latency_ms / 1000.0,
            success=True,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=cost,
            fallback_used=fallback_used,
        )
        self._cache.set(cache_key, response)
        # Strukturierter Gateway-Log (§11.1): keine PII, kein Key, kein Freitext.
        logger.info(
            "%s gateway task=%s backend=%s tokens=%s latency_ms=%.1f fallback=%s grounded=%s",
            REASON,
            task.value,
            used.name,
            response.total_tokens,
            latency_ms,
            fallback_used,
            grounding_report.grounded if grounding_report is not None else "n/a",
        )
        return response
