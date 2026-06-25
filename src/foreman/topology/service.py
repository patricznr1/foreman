# ============================================================
#  FOREMAN — topology/service.py (Sektion I)
#  Zweck: Ableitung der Systemtopologie aus REALEN Quellen — nichts erfunden:
#         (1) Eingänge = distinct data_points.source + jüngste readings-Aktivität;
#         (2) Gedächtnis-Substrat = Health-Probe (best-effort, §9); (3) F7-MCP-
#         Grenze = Ausgang, Aktivität aus dem Audit-Trail (mcp_retrieval). Status
#         nur wo messbar (sonst ehrlich „unbekannt"); benannte Drittsysteme bleiben
#         in der separaten [VISION]-Kategorie und werden NIE als verbunden gezeigt.
#  Architektur-Einordnung: Topologie-Schicht (Schicht 2).
#  Hidden-Term (§8): das Substrat heißt nach außen „Gedächtnis-Substrat" — keine
#         internen Vokabeln in Feldwerten/Labels.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.audit.writer import ACTION_MCP_RETRIEVAL
from foreman.db.models import AuditLog, DataPoint, Reading
from foreman.reads.stream import SIM_SOURCE, STREAM_FRESH_WINDOW
from foreman.substrate.client import SubstrateClient
from foreman.substrate.smoke import run_substrate_smoke
from foreman.topology.schemas import TopologyNode, TopologyView

# Status- und Richtungs-Vokabular (deutsche Domänen-Werte der Studie).
STATUS_CONNECTED = "verbunden"
STATUS_DISTURBED = "gestört"
STATUS_INACTIVE = "inaktiv"
STATUS_UNKNOWN = "unbekannt"
DIR_INBOUND = "liefert"
DIR_OUTBOUND = "liest"
DIR_BOTH = "beides"
DIR_NONE = "keine"

# Sprechende Labels für die realen Ingest-Protokolle.
_SOURCE_LABELS = {
    "opcua": "OPC UA",
    "modbus": "Modbus",
    "mqtt": "MQTT",
    "s7": "S7",
    "simulation": "Simulation (intern)",
}


def _source_label(source: str) -> str:
    return _SOURCE_LABELS.get(source, source)


async def _source_nodes(
    session: AsyncSession, *, now: datetime, fresh_window: timedelta
) -> list[TopologyNode]:
    """Eingangs-Knoten aus distinct data_points.source + jüngster readings-Aktivität."""
    stmt = (
        select(DataPoint.source, func.max(Reading.time))
        .select_from(DataPoint)
        .outerjoin(Reading, Reading.data_point_id == DataPoint.id)
        .where(DataPoint.source.is_not(None))
        .group_by(DataPoint.source)
        .order_by(DataPoint.source)
    )
    nodes: list[TopologyNode] = []
    for source, last_activity in (await session.execute(stmt)).all():
        # Die interne Simulationsquelle IST der Eingangs-Live-Stream (Zwilling als
        # Datenquelle): gegen das ENGE Stream-Fenster gemessen — dieselbe Wahrheit,
        # die das globale „Live"-Badge trägt (§12.6), sodass Kachel und Badge nie
        # auseinanderlaufen. Externe Protokolle behalten das generische Frischefenster.
        window = STREAM_FRESH_WINDOW if source == SIM_SOURCE else fresh_window
        if last_activity is None:
            # Datenpunkte vorhanden, aber nie Daten geflossen → ehrlich unbekannt.
            status = STATUS_UNKNOWN
        elif last_activity >= now - window:
            status = STATUS_CONNECTED
        else:
            status = STATUS_INACTIVE
        nodes.append(
            TopologyNode(
                id=f"source:{source}",
                label=_source_label(source),
                kind="ingest_source",
                direction=DIR_INBOUND,
                status=status,
                last_activity=last_activity,
                internal=(source == SIM_SOURCE),
                detail={"protocol": source},
            )
        )
    return nodes


async def _substrate_node(
    client: SubstrateClient | None, *, now: datetime, probe: bool
) -> TopologyNode:
    """Gedächtnis-Substrat-Knoten — Status aus einer best-effort-Health-Probe (§9)."""

    def _node(status: str, detail: dict[str, Any], last_activity: datetime | None) -> TopologyNode:
        return TopologyNode(
            id="substrate",
            label="Gedächtnis-Substrat",
            kind="substrate",
            direction=DIR_BOTH,
            status=status,
            last_activity=last_activity,
            detail=detail,
        )

    if client is None:
        # Kein Substrat konfiguriert → bewusst nicht verbunden (messbarer Zustand).
        return _node(STATUS_INACTIVE, {"configured": False}, None)
    if not probe:
        # Konfiguriert, aber nicht gemessen → ehrlich unbekannt (kein grün geraten).
        return _node(STATUS_UNKNOWN, {"configured": True, "probed": False}, None)
    try:
        result = await run_substrate_smoke(client)
    except Exception:  # best-effort: ein Substrat-Ausfall darf die Topologie nicht brechen.
        return _node(STATUS_DISTURBED, {"configured": True, "probe_error": True}, None)
    return _node(
        STATUS_CONNECTED if result.ok else STATUS_DISTURBED,
        {"configured": True, "latency_ms": result.latency_ms},
        now,
    )


async def _mcp_node(
    session: AsyncSession,
    *,
    now: datetime,
    configured: bool,
    fresh_window: timedelta,
    include_audit: bool,
) -> TopologyNode:
    """F7-MCP-Grenze (Ausgang) — Aktivität aus dem Audit-Trail (mcp_retrieval).

    Ohne Audit-Einsicht (Schichtleiter) wird der Trail NICHT gelesen: dann nur
    Verbindungsstatus aus der Konfiguration, keine Audit-Details.
    """
    detail: dict[str, Any] = {"configured": configured}
    last_activity: datetime | None = None
    status = STATUS_UNKNOWN if configured else STATUS_INACTIVE

    if include_audit:
        consumer_count = await session.scalar(
            select(func.count(distinct(AuditLog.actor))).where(
                AuditLog.action_type == ACTION_MCP_RETRIEVAL
            )
        )
        last_activity = await session.scalar(
            select(func.max(AuditLog.occurred_at)).where(
                AuditLog.action_type == ACTION_MCP_RETRIEVAL
            )
        )
        detail["consumer_count"] = consumer_count or 0
        if configured:
            if last_activity is not None and last_activity >= now - fresh_window:
                status = STATUS_CONNECTED
            else:
                status = STATUS_INACTIVE

    return TopologyNode(
        id="mcp",
        label="MCP-Schnittstelle (F7)",
        kind="mcp_boundary",
        direction=DIR_OUTBOUND,
        status=status,
        last_activity=last_activity,
        detail=detail,
    )


def _vision_nodes() -> list[TopologyNode]:
    """Illustrative [VISION]-Drittsysteme — benannt, aber NICHT als verbunden gezeigt."""
    note = "geplant — nicht verbunden ([VISION])"
    return [
        TopologyNode(
            id="vision:erp",
            label="ERP",
            kind="vision",
            direction=DIR_NONE,
            status=STATUS_UNKNOWN,
            vision=True,
            detail={"note": note},
        ),
        TopologyNode(
            id="vision:energy_management",
            label="Energiemanagement",
            kind="vision",
            direction=DIR_NONE,
            status=STATUS_UNKNOWN,
            vision=True,
            detail={"note": note},
        ),
        TopologyNode(
            id="vision:simulation_software",
            label="Simulationssoftware (extern)",
            kind="vision",
            direction=DIR_NONE,
            status=STATUS_UNKNOWN,
            vision=True,
            detail={"note": note},
        ),
    ]


async def build_topology(
    session: AsyncSession,
    *,
    substrate_client: SubstrateClient | None,
    mcp_token_configured: bool,
    fresh_window: timedelta,
    probe_substrate: bool,
    include_audit: bool,
) -> TopologyView:
    """Baut die ehrlich abgeleitete Systemtopologie."""
    now = datetime.now(UTC)
    nodes = await _source_nodes(session, now=now, fresh_window=fresh_window)
    nodes.append(await _substrate_node(substrate_client, now=now, probe=probe_substrate))
    nodes.append(
        await _mcp_node(
            session,
            now=now,
            configured=mcp_token_configured,
            fresh_window=fresh_window,
            include_audit=include_audit,
        )
    )
    return TopologyView(nodes=nodes, vision=_vision_nodes(), generated_at=now)
