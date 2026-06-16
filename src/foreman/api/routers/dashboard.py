# ============================================================
#  FOREMAN — api/routers/dashboard.py
#  Zweck: Die zwei HTTP-Read-Routen des Dashboards (F5, Pull/Erstbild): das
#         Flotten-Lagebild (/overview) und der Sensortrend einer Maschine
#         (/machines/{id}/trend). Beide lesen über den geteilten Read-Core und
#         tragen DIESELBE Autorisierung wie der WebSocket-Push (can_subscribe) —
#         so hält der PII-/Scope-Strich auch auf HTTP, nicht nur im Frontend.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Read-only, keine Aktorik.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status

from foreman.api.deps import CurrentUser, SessionDep
from foreman.reads.overview import build_fleet_overview
from foreman.reads.trend import build_trend
from foreman.realtime.authz import can_subscribe, overview_scope
from foreman.realtime.topics import OVERVIEW_TOPIC, machine_topic
from foreman.schemas.dashboard import FleetOverviewOut, MachineTrendOut

router = APIRouter(tags=["dashboard"])

# Grenzen des Trend-Fensters (gegen unbegrenzten Abruf, wie die MCP-Read-Schicht).
_DEFAULT_TREND_HOURS = 24
_MAX_TREND_HOURS = 168  # 7 Tage


@router.get("/overview", response_model=FleetOverviewOut)
async def get_overview(session: SessionDep, user: CurrentUser) -> FleetOverviewOut:
    """Flotten-Lagebild für Statusleiste/Cockpit — scope-korrekt nach Rolle.

    Gleiche Autorisierung wie das WS-`overview`-Thema (manager/shift_lead); andere
    Rollen erhalten 403 statt eines fremden Lagebilds.
    """
    if not await can_subscribe(session, user, OVERVIEW_TOPIC):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Kein Zugriff auf das Flotten-Cockpit"
        )
    scope = await overview_scope(session, user)
    overview = await build_fleet_overview(session, machine_ids=scope)
    return FleetOverviewOut.model_validate(overview)


@router.get("/machines/{machine_id}/trend", response_model=MachineTrendOut)
async def get_machine_trend(
    machine_id: int,
    datapoint: str,
    session: SessionDep,
    user: CurrentUser,
    hours: int = _DEFAULT_TREND_HOURS,
) -> MachineTrendOut:
    """Aggregierter Sensortrend eines Datenpunkts + statisches Normalband.

    Gleiche Maschinen-Scope-Autorisierung wie das WS-`machine`-Thema.
    """
    if not await can_subscribe(session, user, machine_topic(machine_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Kein Zugriff auf diese Maschine"
        )
    bounded_hours = max(1, min(hours, _MAX_TREND_HOURS))
    end = datetime.now(UTC)
    trend = await build_trend(
        session, machine_id, datapoint, start=end - timedelta(hours=bounded_hours), end=end
    )
    if trend is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datenpunkt '{datapoint}' an Maschine {machine_id} nicht gefunden",
        )
    return MachineTrendOut.model_validate(trend)
