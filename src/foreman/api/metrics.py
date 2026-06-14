# ============================================================
#  FOREMAN — api/metrics.py
#  Zweck: GET /metrics im Prometheus-Textformat (GROUND_TRUTH §11.2, ab F4).
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Auf Root-Ebene gemountet
#         (nicht unter /api/v1) und in der Auth-Middleware whitelisted — ein
#         Prometheus-Scraper trägt kein JWT.
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Response

from foreman.observability.metrics import render_metrics

router = APIRouter(tags=["observability"])


@router.get("/metrics")
async def get_metrics() -> Response:
    """Liefert die Prometheus-Metriken (Request-/Latenz-/Drift-Kennzahlen)."""
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)
