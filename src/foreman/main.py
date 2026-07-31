# ============================================================
#  FOREMAN — main.py
#  Zweck: App-Factory + Lifespan (Substrat-Smoke beim Start) + Router-Mounting.
#  Architektur-Einordnung: Einstiegspunkt der FOREMAN-Plattform (Schicht 2).
#  Verhalten (§9): Beim Start läuft der Substrat-Smoke; ein Fehlschlag bricht den
#         Start NICHT ab (Datenaufnahme läuft unabhängig vom Substrat weiter).
# ============================================================
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from math import ceil

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse

from foreman.api import auth, health
from foreman.api import metrics as metrics_api
from foreman.api.middleware import AuthMiddleware
from foreman.api.routers import (
    alarms,
    audit,
    components,
    dashboard,
    data_points,
    lines,
    machines,
    maintenance_events,
    me,
    production_runs,
    readings,
    substrate,
    topology,
    worker_notes,
    ws_ticket,
)
from foreman.archive.router import router as archive_router
from foreman.config import Settings, get_settings
from foreman.db.session import dispose_engine, init_engine
from foreman.llm.errors import BackendUnavailable, GatewayTimeout, RateLimited
from foreman.logging_setup import ALERT, INFO, OK, get_logger, setup_logging
from foreman.notes.router import router as notes_search_router
from foreman.realtime import ws as dashboard_ws
from foreman.realtime.wiring import start_dashboard_push, stop_dashboard_push
from foreman.reasoners.drift import router as drift_router
from foreman.reasoners.event_chain import router as event_chain_router
from foreman.reasoners.failure import router as failure_router
from foreman.substrate.client import SubstrateClient, SubstrateNotConfiguredError
from foreman.substrate.smoke import run_substrate_smoke

logger = get_logger("foreman.main")

# CRUD-/Ingestion-/Substrat-Router unter /api/v1 (§4).
_API_V1_ROUTERS = (
    lines.router,
    machines.router,
    me.router,
    components.router,
    data_points.router,
    production_runs.router,
    maintenance_events.router,
    # F-SEM: die statische Such-Route VOR dem worker_notes-CRUD-Router (sonst fängt
    # `/worker_notes/{note_id}` den Pfad `/worker_notes/search`).
    notes_search_router,
    worker_notes.router,
    alarms.router,
    # Paket 1b: quellenübergreifende Archiv-Suche (Notiz + Wartung + Alarm), additiv.
    archive_router,
    readings.router,
    dashboard.router,
    substrate.router,
    audit.router,
    topology.router,
    drift_router.router,
    event_chain_router.router,
    failure_router.router,
    dashboard_ws.router,
    ws_ticket.router,
)


async def _startup_substrate_smoke(settings: Settings) -> None:
    """Führt den Substrat-Smoke beim Start aus — strikt non-blocking (§9)."""
    try:
        client = SubstrateClient.from_settings(settings)
    except SubstrateNotConfiguredError:
        logger.warning(
            "%s Substrat nicht konfiguriert (SUBSTRATE_BASE_URL fehlt) — Smoke übersprungen",
            INFO,
        )
        return
    try:
        result = await run_substrate_smoke(client)
        logger.info(
            "%s Substrat-Smoke beim Start: ok=%s latency_ms=%s",
            OK if result.ok else ALERT,
            result.ok,
            result.latency_ms,
        )
    except Exception as exc:
        logger.warning("%s Substrat-Smoke beim Start fehlgeschlagen: %s", ALERT, exc)
    finally:
        await client.aclose()


# --- Fehlerabbildung des Modell-Gateways (§11.2/§13.2) ---
# Ohne diese Abbildung endet ein BEKANNTER Betriebszustand — Backend nicht
# erreichbar, Zeitüberschreitung, Kontingent erschöpft — als 500 und sieht damit
# aus wie ein Absturz statt wie eine vorübergehende Einschränkung. Dieselbe Linie
# wie die Archiv-Suche (§15.8): ehrlich degradieren statt hart scheitern.
# `GatewayConfigError` bleibt bewusst ein 500 — eine Fehlkonfiguration IST ein
# Serverfehler und soll nicht als vorübergehend beschönigt werden.
_GATEWAY_UNAVAILABLE_DETAIL = (
    "Die KI-Analyse ist vorübergehend nicht verfügbar. Alarme, Trends und Archiv "
    "sind davon unberührt."
)


async def _gateway_unavailable_handler(_request: Request, exc: Exception) -> JSONResponse:
    """`BackendUnavailable`/`GatewayTimeout` → 503. Details nur ins Log, nie in die
    Antwort (keine Backend-Namen/Konfigurationszustände nach außen)."""
    logger.warning("%s Modell-Gateway nicht verfügbar: %s", ALERT, exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": _GATEWAY_UNAVAILABLE_DETAIL},
    )


async def _gateway_rate_limited_handler(_request: Request, exc: Exception) -> JSONResponse:
    """`RateLimited` → 429 mit `Retry-After` (OWASP LLM10)."""
    # Starlette ruft diesen Handler ausschließlich für den registrierten Typ auf —
    # die Zusicherung engt den `Exception`-Parameter der Handler-Signatur ein,
    # statt einen unerreichbaren Fallback vorzutäuschen.
    assert isinstance(exc, RateLimited)
    retry_after = max(1, ceil(exc.retry_after_s))
    logger.warning("%s Modell-Gateway gedrosselt (retry_after=%ds)", ALERT, retry_after)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Zu viele KI-Analysen in kurzer Zeit. Bitte kurz warten."},
        headers={"Retry-After": str(retry_after)},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Baut die FOREMAN-FastAPI-App."""
    cfg = settings or get_settings()
    setup_logging(cfg.log_level)
    # Fail-Fast: kein Produktionsstart mit schwachem/Default-JWT-Secret (§8/§10.4).
    cfg.require_secure_secrets()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_engine(cfg)
        logger.info("%s FOREMAN startet (env=%s)", INFO, cfg.environment)
        await _startup_substrate_smoke(cfg)
        # Live-Push (F5): ein LISTEN-Listener + Hub pro Worker.
        await start_dashboard_push(app, cfg)
        yield
        await stop_dashboard_push(app)
        await dispose_engine()
        logger.info("%s FOREMAN heruntergefahren", INFO)

    app = FastAPI(
        title="FOREMAN",
        version="0.2.0",
        summary="Production Intelligence with Memory",
        lifespan=lifespan,
    )
    # Auth-Middleware: alles außer /health, /auth/*, OpenAPI-Doku (§4).
    app.add_middleware(AuthMiddleware, settings=cfg)

    # Gateway-Fehler tragen HTTP-Semantik statt 500 (siehe oben).
    app.add_exception_handler(BackendUnavailable, _gateway_unavailable_handler)
    app.add_exception_handler(GatewayTimeout, _gateway_unavailable_handler)
    app.add_exception_handler(RateLimited, _gateway_rate_limited_handler)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(metrics_api.router)  # GET /metrics (Prometheus, §11.2)

    api_v1 = APIRouter(prefix="/api/v1")
    for router in _API_V1_ROUTERS:
        api_v1.include_router(router)
    app.include_router(api_v1)

    return app


app = create_app()
