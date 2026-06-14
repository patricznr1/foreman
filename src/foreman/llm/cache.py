# ============================================================
#  FOREMAN — llm/cache.py
#  Zweck: Deterministisches Antwort-Caching des Gateways (F-LLM). Cache-Key aus
#         Modell + normalisiertem Prompt + Parametern + Quellen, SHA-256-gehasht
#         (keine PII im Key, §8). In Tests erzwingt es Byte-Determinismus; im
#         Betrieb optional zuschaltbar (config.cache_enabled).
#  Architektur-Einordnung: Querschnitt der LLM-Schicht (Schicht 2). In-Memory;
#         der Gateway prüft den Cache vor dem Backend-Call und markiert beim
#         Lesen `from_cache=True`.
#  Konvention (§6): deutsche Kommentare; keine PII/Keys persistiert (nur Hash).
# ============================================================
from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

# Nur für Annotationen importiert (Laufzeit: Duck-Typing) — bricht den
# Importzyklus cache ↔ gateway, da der LiteLLMGateway diese cache-Klasse nutzt.
if TYPE_CHECKING:
    from foreman.llm.gateway import GatewayResponse, Task
    from foreman.llm.grounding import GroundingSource


class ResponseCache:
    """In-Memory-Cache für GatewayResponses, key = gehashter Logik-Input.

    Bewusst über die LOGISCHEN Eingaben gekeyt (nicht über den gespotlighteten
    Prompt mit Zufalls-Delimiter) — so bleibt der Cache trotz randomisiertem
    Spotlighting deterministisch.
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._store: dict[str, GatewayResponse] = {}

    @staticmethod
    def make_key(
        *,
        model: str,
        task: Task,
        system_prompt: str,
        user_prompt: str,
        sources: Sequence[GroundingSource] | None,
        temperature: float,
        max_tokens: int | None,
    ) -> str:
        """Baut den deterministischen, PII-freien (gehashten) Cache-Key."""
        payload = {
            "model": model,
            "task": task.value,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "sources": [[s.source_id, s.content, s.trusted] for s in (sources or ())],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get(self, key: str) -> GatewayResponse | None:
        """Liefert die gecachte Antwort (mit from_cache=True) oder None."""
        if not self._enabled:
            return None
        cached = self._store.get(key)
        if cached is None:
            return None
        return cached.model_copy(update={"from_cache": True})

    def set(self, key: str, response: GatewayResponse) -> None:
        """Legt eine Antwort im Cache ab (im Quell-Zustand from_cache=False)."""
        if not self._enabled:
            return
        self._store[key] = response
