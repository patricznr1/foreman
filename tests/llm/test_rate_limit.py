# ============================================================
#  FOREMAN — tests/llm/test_rate_limit.py
#  Zweck: Pflicht-Test-Block für den Token-Bucket-Rate-Limiter (F-LLM,
#         OWASP LLM10). Prüft: Bucket erschöpft/refillt mit seedbarer Uhr,
#         RateLimiter wirft RateLimited mit retry_after, Backend-Isolation.
#  Architektur-Einordnung: Quality Gate §10.3. Reine Unit-Tests (seedbare
#         Uhr statt echter Zeit — §6 reine, seedbare Funktionen).
# ============================================================
from __future__ import annotations

import pytest

from foreman.llm.errors import RateLimited
from foreman.llm.rate_limit import RateLimiter, TokenBucket


class _Clock:
    """Seedbare monotone Uhr für deterministische Rate-Limit-Tests."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_token_bucket_erschoepft_nach_kapazitaet() -> None:
    clock = _Clock()
    bucket = TokenBucket(capacity=3, refill_per_s=1.0, now_fn=clock)
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is True
    # Vierter Zugriff ohne Zeitfortschritt → verweigert.
    assert bucket.try_acquire() is False


def test_token_bucket_refillt_mit_der_zeit() -> None:
    clock = _Clock()
    bucket = TokenBucket(capacity=2, refill_per_s=1.0, now_fn=clock)
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False
    clock.advance(2.0)  # +2 Tokens
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False


def test_token_bucket_refill_ist_gedeckelt() -> None:
    clock = _Clock()
    bucket = TokenBucket(capacity=2, refill_per_s=1.0, now_fn=clock)
    clock.advance(100.0)  # darf nicht über die Kapazität hinaus auffüllen
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False


def test_rate_limiter_wirft_rate_limited_mit_retry_after() -> None:
    clock = _Clock()
    limiter = RateLimiter(capacity=1, refill_per_s=0.5, now_fn=clock)
    limiter.check("local")  # erstes Token ok
    with pytest.raises(RateLimited) as exc:
        limiter.check("local")
    # Bei 0.5 Token/s und Defizit 1 → ~2 s bis zum nächsten Token.
    assert exc.value.retry_after_s == pytest.approx(2.0, abs=0.01)


def test_rate_limiter_isoliert_backends() -> None:
    clock = _Clock()
    limiter = RateLimiter(capacity=1, refill_per_s=1.0, now_fn=clock)
    limiter.check("local")
    # local ist erschöpft, cloud hat seinen eigenen Bucket.
    with pytest.raises(RateLimited):
        limiter.check("local")
    limiter.check("cloud")  # darf NICHT werfen
