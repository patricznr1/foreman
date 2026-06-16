# ============================================================
#  FOREMAN — realtime/ws.py
#  Zweck: Der EINE gemultiplexte WebSocket-Endpoint des Dashboards (F5,
#         /api/v1/ws). Ein Client, viele Themen-Abos über EINE Verbindung. Auth
#         per Query-Token (die AuthMiddleware lässt WS-Scope durch — §middleware),
#         danach pro subscribe eine AUTORISIERUNG (Rollenmatrix + Scope, authz):
#         default-deny, sonst sofortiger Snapshot + danach Live-Deltas über den
#         Hub. Geladen wird scope-korrekt über den Read-Core (keine Aktorik).
#  Frische statt Einfrieren (Review-Fix): NICHT das beim Connect geladene User-
#         Objekt herumreichen, sondern nur die `user_id` (aus dem Token). Vor JEDEM
#         Snapshot UND JEDEM Push wird der Nutzer frisch geladen und erneut
#         autorisiert — wird einem Nutzer mid-session der Scope entzogen, fällt das
#         Abo beim nächsten Delta (kein PII-Weiterstrom bis Reconnect, Vorgabe 2).
#  Robustheit (Review-Fix): der Push-Loop fängt transiente Fehler ab und läuft
#         weiter (kein lautloser Zombie); bei totem Socket bricht er sauber ab,
#         sodass das Cleanup (hub.remove) immer greift.
#  Architektur-Einordnung: Live-Push-Layer (F5), Transport-Kante. Hält keine
#         Dauer-Session — pro Operation eine kurze Read-only-Session (wie die
#         MCP-Schicht), damit eine WS-Verbindung keine Pool-Verbindung blockiert.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast

import jwt
from fastapi import APIRouter, FastAPI, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.api.deps import SettingsDep
from foreman.core.security import decode_access_token
from foreman.db.models import User
from foreman.db.session import get_sessionmaker
from foreman.logging_setup import ALERT, get_logger
from foreman.reads.overview import build_fleet_overview
from foreman.reads.trend import build_trend_by_id
from foreman.realtime.authz import can_subscribe, overview_scope
from foreman.realtime.hub import DashboardHub, Subscription
from foreman.realtime.topics import parse_topic
from foreman.realtime.wiring import get_hub
from foreman.schemas.dashboard import FleetOverviewOut, MachineStatusOut, MachineTrendOut

logger = get_logger("foreman.realtime.ws")
router = APIRouter()

# Fenster für den Trend-Snapshot/-Push (Erstbild + Nachrücken).
_TREND_WINDOW = timedelta(hours=1)
# WS-Close-Code für Auth-Fehler (4000-4999 = anwendungsdefiniert).
_WS_UNAUTHORIZED = 4401


@asynccontextmanager
async def _read_session() -> AsyncIterator[AsyncSession]:
    """Kurze Read-only-Session pro Operation (kein Commit, keine Aktorik)."""
    async with get_sessionmaker()() as session:
        yield session


@router.websocket("/ws")
async def dashboard_ws(
    websocket: WebSocket,
    settings: SettingsDep,
    token: Annotated[str | None, Query()] = None,
) -> None:
    """Gemultiplexter Dashboard-Stream: authentifizieren, dann Themen abonnieren."""
    user_id = await _authenticate(websocket, settings, token)
    if user_id is None:
        return  # close wurde in _authenticate gesendet
    await websocket.accept()
    hub = get_hub(cast(FastAPI, websocket.app))
    subscription = hub.register()
    push_task = asyncio.create_task(_push_loop(websocket, hub, subscription, user_id))
    try:
        await _receive_loop(websocket, hub, subscription, user_id)
    except WebSocketDisconnect:
        pass
    finally:
        push_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await push_task
        hub.remove(subscription)


async def _authenticate(
    websocket: WebSocket, settings: SettingsDep, token: str | None
) -> int | None:
    """Validiert das Query-Token und liefert die user_id (schließt bei Fehler vor accept).

    Gibt bewusst nur die ID zurück, nicht das User-Objekt — Rolle/Scope werden pro
    Snapshot/Push frisch geladen (kein eingefrorener Autorisierungs-Stand).
    """
    if not token:
        await websocket.close(code=_WS_UNAUTHORIZED)
        return None
    try:
        payload = decode_access_token(token, settings)
    except jwt.InvalidTokenError:
        await websocket.close(code=_WS_UNAUTHORIZED)
        return None
    subject = payload.get("sub")
    if subject is None:
        await websocket.close(code=_WS_UNAUTHORIZED)
        return None
    user_id = int(subject)
    async with _read_session() as session:
        exists = await session.get(User, user_id) is not None
    if not exists:
        await websocket.close(code=_WS_UNAUTHORIZED)
        return None
    return user_id


async def _receive_loop(
    websocket: WebSocket, hub: DashboardHub, subscription: Subscription, user_id: int
) -> None:
    """Verarbeitet subscribe/unsubscribe-Nachrichten des Clients."""
    while True:
        message = await websocket.receive_json()
        if not isinstance(message, dict):
            continue
        topic = message.get("topic")
        if not isinstance(topic, str):
            continue
        action = message.get("action")
        if action == "subscribe":
            await _handle_subscribe(websocket, hub, subscription, user_id, topic)
        elif action == "unsubscribe":
            hub.unsubscribe(subscription, topic)


async def _handle_subscribe(
    websocket: WebSocket, hub: DashboardHub, subscription: Subscription, user_id: int, topic: str
) -> None:
    """Autorisiert (default-deny, frischer User) und sendet bei Erfolg den Snapshot."""
    async with _read_session() as session:
        allowed, payload = await _authorized_payload(session, user_id, topic)
    if not allowed:
        await websocket.send_json({"type": "error", "topic": topic, "reason": "forbidden"})
        return
    hub.subscribe(subscription, topic)
    if payload is not None:
        await websocket.send_json({"type": "update", "topic": topic, "data": payload})


async def _push_loop(
    websocket: WebSocket, hub: DashboardHub, subscription: Subscription, user_id: int
) -> None:
    """Lädt nach jedem (debouncten) Hub-Signal scope-korrekt und pusht — robust.

    Transiente Fehler (DB-Hiccup) beenden den Loop NICHT (kein lautloser Zombie);
    ein toter Socket bricht ihn sauber ab, sodass das Cleanup greift.
    """
    while True:
        try:
            topic = await subscription.next_dirty()
            await _send_topic(websocket, hub, subscription, user_id, topic)
        except (WebSocketDisconnect, RuntimeError):
            break  # Socket geschlossen — Loop beenden, Cleanup im finally des Endpoints
        except Exception:
            logger.exception("%s Dashboard-Push fehlgeschlagen — Verbindung bleibt live", ALERT)


async def _send_topic(
    websocket: WebSocket, hub: DashboardHub, subscription: Subscription, user_id: int, topic: str
) -> None:
    """Pusht ein Thema — mit frischer Re-Autorisierung (entzogener Scope → Abo weg)."""
    async with _read_session() as session:
        allowed, payload = await _authorized_payload(session, user_id, topic)
    if not allowed:
        # Scope mid-session entzogen (oder Nutzer gelöscht): Abo fallen lassen.
        hub.unsubscribe(subscription, topic)
        await websocket.send_json({"type": "error", "topic": topic, "reason": "forbidden"})
        return
    if payload is not None:
        await websocket.send_json({"type": "update", "topic": topic, "data": payload})


async def _authorized_payload(
    session: AsyncSession, user_id: int, topic: str
) -> tuple[bool, dict[str, Any] | None]:
    """Lädt den Nutzer FRISCH, prüft die Autorisierung (default-deny) und lädt die Sicht.

    Gibt `(allowed, payload)` zurück — `payload` ist None, wenn erlaubt, aber (noch)
    keine Daten vorliegen. Eine Wahrheit für Snapshot (subscribe) und Push.
    """
    user = await session.get(User, user_id)
    if user is None or not await can_subscribe(session, user, topic):
        return False, None
    return True, await _load_topic(session, user, topic)


async def _load_topic(session: AsyncSession, user: User, topic: str) -> dict[str, Any] | None:
    """Lädt die scope-korrekte Sicht eines (bereits autorisierten) Themas."""
    kind, entity_id = parse_topic(topic)
    if kind == "overview":
        scope = await overview_scope(session, user)
        overview = await build_fleet_overview(session, machine_ids=scope)
        return FleetOverviewOut.model_validate(overview).model_dump(mode="json")
    if kind == "machine" and entity_id is not None:
        overview = await build_fleet_overview(session, machine_ids=[entity_id])
        if not overview.machines:
            return None
        return MachineStatusOut.model_validate(overview.machines[0]).model_dump(mode="json")
    if kind == "trend" and entity_id is not None:
        end = datetime.now(UTC)
        trend = await build_trend_by_id(session, entity_id, start=end - _TREND_WINDOW, end=end)
        if trend is None:
            return None
        return MachineTrendOut.model_validate(trend).model_dump(mode="json")
    return None
