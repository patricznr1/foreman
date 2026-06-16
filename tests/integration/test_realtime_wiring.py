# ============================================================
#  FOREMAN — tests/integration/test_realtime_wiring.py
#  Zweck: App-Verdrahtung des Live-Push-Layers (F5) — get_hub ist pro App stabil
#         (ein Hub je Worker), und start/stop_dashboard_push hängt eine echte
#         LISTEN-Verbindung an bzw. räumt sie wieder ab.
# ============================================================
from __future__ import annotations

import pytest
from fastapi import FastAPI

from foreman.config import Settings
from foreman.realtime.hub import DashboardHub
from foreman.realtime.wiring import get_hub, start_dashboard_push, stop_dashboard_push

pytestmark = pytest.mark.integration


def test_get_hub_is_stable_per_app() -> None:
    app = FastAPI()
    hub = get_hub(app)
    assert isinstance(hub, DashboardHub)
    assert get_hub(app) is hub  # idempotent: ein Hub pro App/Worker


async def test_start_stop_dashboard_push_attaches_and_clears_listener(
    test_settings: Settings,
) -> None:
    app = FastAPI()
    await start_dashboard_push(app, test_settings)
    try:
        assert isinstance(get_hub(app), DashboardHub)
        assert app.state.dashboard_listener is not None
    finally:
        await stop_dashboard_push(app)
