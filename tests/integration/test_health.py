# ============================================================
#  FOREMAN — tests/integration/test_health.py
#  Zweck: Health-Check ist offen (kein Token) und liefert 200 (§4).
# ============================================================
from __future__ import annotations

from httpx import AsyncClient


async def test_health_is_open_and_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "foreman"
