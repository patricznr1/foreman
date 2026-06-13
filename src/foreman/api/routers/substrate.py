# ============================================================
#  FOREMAN — api/routers/substrate.py
#  Zweck: Substrat-Smoke-Endpunkt (GET /api/v1/substrate/smoke), §9.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Meldet den remember→recall-
#         Round-Trip als {ok, latency_ms}. Nicht konfiguriert / Fehlschlag →
#         {ok:false, ...}, kein Server-Fehler (Fallback §9).
# ============================================================
from __future__ import annotations

from fastapi import APIRouter

from foreman.api.deps import SubstrateClientDep
from foreman.schemas.substrate import SubstrateSmokeResult
from foreman.substrate.smoke import run_substrate_smoke

router = APIRouter(prefix="/substrate", tags=["substrate"])


@router.get("/smoke", response_model=SubstrateSmokeResult)
async def substrate_smoke(client: SubstrateClientDep) -> SubstrateSmokeResult:
    """Führt den Substrat-Round-Trip aus und liefert {ok, latency_ms}."""
    if client is None:
        return SubstrateSmokeResult(
            ok=False,
            latency_ms=0.0,
            detail="Substrat nicht konfiguriert (SUBSTRATE_BASE_URL fehlt)",
        )
    return await run_substrate_smoke(client)
