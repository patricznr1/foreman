# ============================================================
#  FOREMAN — realtime/listener.py
#  Zweck: Der LISTEN-Consumer (F5) EINES Workers. Hält eine dedizierte asyncpg-
#         Verbindung auf DASHBOARD_CHANNEL, decodiert eingehende NOTIFYs und kippt
#         sie in den Hub. Bricht die Verbindung ab, baut der Listener sie neu auf
#         und signalisiert ein breites Refresh (Snapshot-Reload) — so füllt sich
#         die Lücke des fire-and-forget-NOTIFY beim Reconnect wieder auf.
#  Architektur-Einordnung: Live-Push-Layer (F5), Consumer-Seite, PRO Worker. Eine
#         eigene LISTEN-Verbindung je Worker (NICHT aus dem SQLAlchemy-Pool —
#         LISTEN braucht eine langlebige, dedizierte Verbindung). Postgres
#         broadcastet NOTIFY an alle Worker; jeder bedient seine eigenen Clients.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

import asyncio
import contextlib

import asyncpg

from foreman.logging_setup import ALERT, OK, get_logger
from foreman.realtime.channels import DASHBOARD_CHANNEL, ChangeSet, decode_change
from foreman.realtime.hub import DashboardHub

logger = get_logger("foreman.realtime.listener")

# Wartezeit vor dem Wiederverbinden nach Verbindungsverlust.
DEFAULT_RECONNECT_SECONDS = 2.0


class DashboardListener:
    """Speist NOTIFYs aus Postgres in den Hub; verbindet sich nach Abbruch neu."""

    def __init__(
        self, dsn: str, hub: DashboardHub, *, reconnect_seconds: float = DEFAULT_RECONNECT_SECONDS
    ) -> None:
        self._dsn = dsn
        self._hub = hub
        self._reconnect_seconds = reconnect_seconds
        self._conn: asyncpg.Connection | None = None
        self._task: asyncio.Task[None] | None = None
        self._closing = False
        # Gesetzt, sobald die LISTEN-Verbindung steht — start() wartet darauf, damit
        # ein unmittelbar folgendes NOTIFY nicht ins Leere läuft (fire-and-forget).
        self._ready = asyncio.Event()

    async def start(self) -> None:
        """Startet die LISTEN-Schleife und wartet, bis sie verbunden ist.

        Wartet bis zu 5 s auf die erste Verbindung — kommt sie nicht (DB nicht
        erreichbar), läuft der Start trotzdem weiter (der Task verbindet im
        Hintergrund neu), blockiert also den App-Start nicht.
        """
        if self._task is None:
            self._closing = False
            self._ready.clear()
            self._task = asyncio.create_task(self._run())
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._ready.wait(), timeout=5.0)

    async def stop(self) -> None:
        """Beendet die Schleife und schließt die Verbindung sauber."""
        self._closing = True
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._close_connection()

    def _on_notify(self, _conn: object, _pid: int, _channel: str, payload: str) -> None:
        """asyncpg-Callback: decodiert den Payload und kippt ihn in den Hub.

        Defensiv: ein kaputter Payload darf den Listener nie umbringen.
        """
        try:
            self._hub.dispatch(decode_change(payload))
        except Exception:  # pragma: no cover - reiner Schutzmantel
            logger.exception("%s NOTIFY-Verarbeitung fehlgeschlagen", ALERT)

    async def _run(self) -> None:
        while not self._closing:
            disconnected = asyncio.Event()
            try:
                self._conn = await asyncpg.connect(self._dsn)
                # Verbindungsabbruch ereignisgesteuert erkennen (kein Busy-Wait).
                self._conn.add_termination_listener(lambda _conn, _ev=disconnected: _ev.set())
                await self._conn.add_listener(DASHBOARD_CHANNEL, self._on_notify)
                logger.info("%s Dashboard-LISTEN verbunden (Kanal %s)", OK, DASHBOARD_CHANNEL)
                # (Re)Connect: breites Refresh — Snapshot-Reload, keine Lücke.
                self._hub.dispatch(ChangeSet(broad=True))
                self._ready.set()
                await disconnected.wait()
            except (asyncpg.PostgresError, OSError) as exc:
                logger.warning("%s Dashboard-LISTEN-Verbindung verloren: %s", ALERT, exc)
            finally:
                await self._close_connection()
            if not self._closing:
                await asyncio.sleep(self._reconnect_seconds)

    async def _close_connection(self) -> None:
        conn = self._conn
        self._conn = None
        if conn is not None and not conn.is_closed():
            with contextlib.suppress(Exception):
                await conn.close(timeout=2.0)
