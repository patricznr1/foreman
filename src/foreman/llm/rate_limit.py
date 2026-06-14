# ============================================================
#  FOREMAN — llm/rate_limit.py
#  Zweck: Token-Bucket-Rate-Limiter pro Backend (F-LLM, OWASP LLM10 —
#         Schutz vor Runaway-Kosten/Last). Seedbare Uhr (now_fn) → ohne Netz
#         und ohne echte Wartezeit testbar (§6: reine, seedbare Funktionen).
#  Architektur-Einordnung: Querschnitt der LLM-Schicht (Schicht 2). Vom Gateway
#         vor jedem Backend-Versuch befragt; bei Erschöpfung wird ein typisierter
#         RateLimited (mit retry_after) hochgereicht.
#  Konvention (§6): deutsche Kommentare/Meldungen.
# ============================================================
from __future__ import annotations

import time
from collections.abc import Callable

from foreman.llm.errors import RateLimited


class TokenBucket:
    """Klassischer Token-Bucket: `capacity` Tokens, Nachfüllung `refill_per_s`.

    Startet voll. `try_acquire` ist rein (kein Sleep) — der Aufrufer entscheidet,
    was bei Verweigerung passiert. Die Uhr ist injizierbar (Default monotonic).
    """

    def __init__(
        self,
        capacity: int,
        refill_per_s: float,
        *,
        now_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._capacity = float(capacity)
        self._refill_per_s = refill_per_s
        self._now = now_fn
        self._tokens = float(capacity)
        self._last = now_fn()

    def _refill(self) -> None:
        now = self._now()
        elapsed = now - self._last
        self._last = now
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_s)

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Entnimmt `tokens`, wenn verfügbar; sonst False (ohne Mutation)."""
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    def retry_after_s(self, tokens: float = 1.0) -> float:
        """Schätzt, nach wie vielen Sekunden `tokens` wieder verfügbar sind."""
        deficit = tokens - self._tokens
        if deficit <= 0:
            return 0.0
        return deficit / self._refill_per_s


class RateLimiter:
    """Hält je Backend einen eigenen Token-Bucket (Backend-Isolation)."""

    def __init__(
        self,
        capacity: int,
        refill_per_s: float,
        *,
        now_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._capacity = capacity
        self._refill_per_s = refill_per_s
        self._now = now_fn
        self._buckets: dict[str, TokenBucket] = {}

    def _bucket(self, backend_name: str) -> TokenBucket:
        bucket = self._buckets.get(backend_name)
        if bucket is None:
            bucket = TokenBucket(self._capacity, self._refill_per_s, now_fn=self._now)
            self._buckets[backend_name] = bucket
        return bucket

    def check(self, backend_name: str) -> None:
        """Entnimmt ein Token für `backend_name`; wirft RateLimited bei Erschöpfung."""
        bucket = self._bucket(backend_name)
        if not bucket.try_acquire():
            raise RateLimited(
                f"❌ Rate-Limit für Backend '{backend_name}' erreicht",
                retry_after_s=bucket.retry_after_s(),
            )
