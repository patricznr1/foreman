# ============================================================
#  FOREMAN — realtime/wiring.py
#  Zweck: Verdrahtung des Live-Push-Layers (F5) mit der FastAPI-App. Ein Hub +
#         ein LISTEN-Listener PRO Worker (kein globaler Singleton) — auf app.state
#         abgelegt, im Lifespan gestartet/gestoppt. `get_hub` legt den Hub bei
#         Bedarf lazy an, sodass der WS-Endpoint ihn auch ohne gelaufenen Lifespan
#         (z. B. im Test) findet; läuft der Lifespan, füttert der Listener genau
#         diesen Hub.
#  Architektur-Einordnung: Live-Push-Layer (F5), App-Verdrahtung (kennt FastAPI —
#         daher getrennt von hub.py/listener.py, die transport-frei bleiben).
#  Multi-Worker: jeder Uvicorn-Worker baut hier seinen eigenen Hub + seine eigene
#         LISTEN-Verbindung; Postgres broadcastet NOTIFY an alle.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from fastapi import FastAPI

from foreman.config import Settings
from foreman.realtime.hub import DashboardHub
from foreman.realtime.listener import DashboardListener


def dsn_for_listen(settings: Settings) -> str:
    """Roher asyncpg-DSN aus der SQLAlchemy-URL — LISTEN braucht eine eigene Verbindung."""
    return settings.database_url.replace("+asyncpg", "")


def get_hub(app: FastAPI) -> DashboardHub:
    """Liefert den Worker-Hub der App (legt ihn bei Bedarf lazy an)."""
    hub = getattr(app.state, "dashboard_hub", None)
    if not isinstance(hub, DashboardHub):
        hub = DashboardHub()
        app.state.dashboard_hub = hub
    return hub


async def start_dashboard_push(app: FastAPI, settings: Settings) -> None:
    """Startet die LISTEN-Verbindung dieses Workers, die den Hub füttert."""
    hub = get_hub(app)
    listener = DashboardListener(dsn_for_listen(settings), hub)
    await listener.start()
    app.state.dashboard_listener = listener


async def stop_dashboard_push(app: FastAPI) -> None:
    """Stoppt die LISTEN-Verbindung dieses Workers (Shutdown)."""
    listener = getattr(app.state, "dashboard_listener", None)
    if isinstance(listener, DashboardListener):
        await listener.stop()
