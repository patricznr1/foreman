# ============================================================
#  FOREMAN — tests/integration/test_metrics_endpoint.py
#  Zweck: Pflicht-Test-Block für den /metrics-Endpunkt (F4, §11.2).
#  Prüft: GET /metrics liefert Prometheus-Textformat inkl. der Drift-Kennzahlen
#  (Events, Detektionsverzug, Fehlalarm-Zähler); ohne Auth erreichbar
#  (Prometheus-Scraper hat kein JWT) — der Pfad ist in der Auth-Whitelist.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration).
# ============================================================
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_metrics_liefert_prometheus_format_mit_drift_kennzahlen(
    client: AsyncClient,
) -> None:
    # /metrics ist ohne Bearer-Token erreichbar (Auth-Whitelist, §11.2).
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")

    body = resp.text
    # Drift-spezifische Kennzahlen (label-los → immer im Output, auch bei 0).
    assert "foreman_drift_events_total" in body
    assert "foreman_drift_detection_delay_seconds" in body
    assert "foreman_drift_false_alarms_total" in body
    # HELP-/TYPE-Zeilen belegen das Prometheus-Textformat.
    assert "# HELP foreman_drift_events_total" in body
    assert "# TYPE foreman_drift_events_total counter" in body


async def test_metrics_ohne_token_nicht_401(client: AsyncClient) -> None:
    # Gegenprobe: ein geschützter Pfad gibt ohne Token 401, /metrics aber nicht.
    protected = await client.get("/api/v1/lines")
    assert protected.status_code == 401
    metrics = await client.get("/metrics")
    assert metrics.status_code == 200
