# ============================================================
#  FOREMAN — mcp/server.py
#  Zweck: Der MCP-Server (F7) — FOREMAN als offener Knoten. Registriert die
#         read-only Tools (Tool-Registry), läuft remote über Streamable HTTP und
#         liegt hinter der MCP-Auth-Middleware. Eigene /health- und /metrics-Routen
#         (foreman_mcp_* erscheint im selben Prozess unter /metrics).
#  Architektur-Einordnung: MCP-Schicht (F7), Schnittstellen-Server. Eigenständige
#         ASGI-App — berührt die Plattform-FastAPI-App NICHT (saubere Trennung,
#         eigener Token, eigener Port).
#  Invariante I (Brief §2): ausschließlich read-only Tools, alle mit
#         readOnlyHint=True; keine Aktorik, kein Reasoner-/LLM-Trigger.
#  Invariante III: Tool-Namen/-Beschreibungen ohne internes Vokabular (Hidden-Term-Scan).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from foreman.config import get_settings
from foreman.db.session import dispose_engine, init_engine
from foreman.logging_setup import INFO, OK, get_logger, setup_logging
from foreman.mcp import tools
from foreman.mcp.auth import McpAuthMiddleware, McpSettings, get_mcp_settings
from foreman.observability.metrics import render_metrics

logger = get_logger("foreman.mcp.server")

SERVER_NAME = "foreman"
# Nach außen sichtbare Server-Beschreibung — bewusst paraphrasiert, ohne internes
# Vokabular (Invariante III) und mit dem Transparenz-/Read-only-Vertrag (Art. 50).
SERVER_INSTRUCTIONS = (
    "FOREMAN — Produktions-Intelligenz mit Langzeitgedächtnis. Dieser Server reicht die "
    "aggregierten Erkenntnisse ausschließlich lesend an Drittsysteme: Maschinen-Stammdaten "
    "und Status, aggregierte Sensortrends, Alarme und Drift-Lage, gespeicherte Ausfall-"
    "Einschätzungen, Werker-Empfehlungen, Ereignisketten-Erklärungen und eine semantische "
    "Notiz-Suche. KI-stämmige Ausgaben tragen maschinenlesbare Transparenz-Flags "
    "(ai_generated, generated_by, requires_human_review, model_version) und — bei "
    "Einschätzungen und Empfehlungen — ihren Validierungs-Vorbehalt. Der Server schaltet "
    "nichts und löst keine Berechnung aus; alle Werte sind vom Betreiber zu prüfen."
)

# Alle Tools sind read-only, nicht destruktiv, idempotent, geschlossene Welt.
_READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)

# (Tool-Funktion, Name, Beschreibung) — Beschreibungen IP-wort-diszipliniert.
_TOOL_SPECS: tuple[tuple[Callable[..., Any], str, str], ...] = (
    (
        tools.list_machines,
        "list_machines",
        "Listet die Maschinen mit Stammdaten und aktuellem Status "
        "(gesund, Drift aktiv oder offene Warnung).",
    ),
    (
        tools.get_machine,
        "get_machine",
        "Liefert eine einzelne Maschine samt Stammdaten und aktuellem Status.",
    ),
    (
        tools.get_drift_status,
        "get_drift_status",
        "Liefert die aktuelle Drift-Lage einer Maschine: offene, noch nicht "
        "quittierte Verhaltens-Warnungen.",
    ),
    (
        tools.get_alarms,
        "get_alarms",
        "Liest Alarme (inklusive Drift-Warnungen), optional gefiltert nach Maschine, "
        "Zeitpunkt und Schweregrad.",
    ),
    (
        tools.list_failure_predictions,
        "list_failure_predictions",
        "Listet gespeicherte Ausfall-Einschätzungen; jede trägt ihren Validierungs-Vorbehalt mit.",
    ),
    (
        tools.get_failure_prediction,
        "get_failure_prediction",
        "Liefert eine einzelne gespeicherte Ausfall-Einschätzung samt Transparenz-Flags.",
    ),
    (
        tools.get_worker_recommendation,
        "get_worker_recommendation",
        "Liefert die gespeicherte Handlungs-Empfehlung zu einer Einschätzung samt Vorbehalt.",
    ),
    (
        tools.list_event_chains,
        "list_event_chains",
        "Listet gespeicherte Ereignisketten-Erklärungen mit ihren Vertrauens-Markern.",
    ),
    (
        tools.get_event_chain,
        "get_event_chain",
        "Liefert eine einzelne gespeicherte Ereignisketten-Erklärung.",
    ),
    (
        tools.search_notes,
        "search_notes",
        "Sucht semantisch ähnliche Schicht-Notizen; der Text ist maskiert, "
        "der Verfasser pseudonym.",
    ),
    (
        tools.get_readings,
        "get_readings",
        "Liefert den aggregierten Sensortrend eines Datenpunkts über die letzten Stunden.",
    ),
)


def build_mcp_server(*, mcp_settings: McpSettings | None = None) -> FastMCP:
    """Baut den FastMCP-Server mit allen read-only Tools (Tool-Registry)."""
    settings = mcp_settings or get_mcp_settings()
    server: FastMCP = FastMCP(
        SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        host=settings.host,
        port=settings.port,
        stateless_http=True,
        json_response=True,
    )
    for fn, name, description in _TOOL_SPECS:
        server.add_tool(fn, name=name, description=description, annotations=_READ_ONLY)
    return server


async def _health(_request: Request) -> JSONResponse:
    """Liveness-Probe (offen, kein Token) — für Lastverteiler/Container-Health."""
    return JSONResponse({"status": "ok", "service": "foreman-mcp"})


async def _metrics(_request: Request) -> Response:
    """Prometheus-Scrape (offen, kein Token) — enthält die foreman_mcp_*-Kennzahlen."""
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


def build_mcp_app(*, mcp_settings: McpSettings | None = None) -> Starlette:
    """Baut die remote erreichbare ASGI-App: Auth-Middleware + MCP-Transport + /health/-metrics."""
    settings = mcp_settings or get_mcp_settings()
    server = build_mcp_server(mcp_settings=settings)
    streamable = server.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        # DB-Engine für die read-only Tool-Sessions; MCP-Session-Manager für den Transport.
        init_engine(get_settings())
        async with server.session_manager.run():
            logger.info("%s FOREMAN MCP-Server bereit (read-only, Port %s)", OK, settings.port)
            yield
        await dispose_engine()
        logger.info("%s FOREMAN MCP-Server heruntergefahren", INFO)

    app = Starlette(
        routes=[
            Route("/health", _health, methods=["GET"]),
            Route("/metrics", _metrics, methods=["GET"]),
            # Der MCP-Transport (Streamable HTTP) unter /mcp — alles außerhalb von
            # /health und /metrics liegt hinter dem MCP-Token.
            Mount("/", app=streamable),
        ],
        lifespan=lifespan,
    )
    app.add_middleware(McpAuthMiddleware, settings=settings)
    return app


def main() -> None:  # pragma: no cover — Prozess-Einstiegspunkt
    """Startet den MCP-Server (Streamable HTTP). Bricht ab, wenn der Token unsicher ist."""
    import uvicorn

    setup_logging(get_settings().log_level)
    mcp_settings = get_mcp_settings()
    # Fail-Fast: kein remote erreichbarer Read-Server ohne sicheren Token (§8/§10.4).
    mcp_settings.require_secure_token(is_production=get_settings().is_production)
    app = build_mcp_app(mcp_settings=mcp_settings)
    uvicorn.run(app, host=mcp_settings.host, port=mcp_settings.port)


if __name__ == "__main__":  # pragma: no cover
    main()
