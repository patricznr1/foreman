# ============================================================
#  FOREMAN — api/health.py
#  Zweck: Offener Health-Check (GET /health), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Kein Auth, keine DB —
#         signalisiert nur, dass der ASGI-Prozess lebt.
# ============================================================
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liefert 200 mit Status, solange die App läuft."""
    return {"status": "ok", "service": "foreman"}
