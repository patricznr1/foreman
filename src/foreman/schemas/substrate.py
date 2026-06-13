# ============================================================
#  FOREMAN — schemas/substrate.py
#  Zweck: Ergebnis-Schema des Substrat-Smoke-Tests.
#  Architektur-Einordnung: API-Vertrag von GET /api/v1/substrate/smoke (§9).
# ============================================================
from __future__ import annotations

from pydantic import BaseModel


class SubstrateSmokeResult(BaseModel):
    """Ergebnis des remember→recall-Round-Trips: {ok, latency_ms}."""

    ok: bool
    latency_ms: float
    detail: str | None = None
