# ============================================================
#  FOREMAN — api/routers/topology.py (Sektion I)
#  Zweck: Read-API der Systemtopologie — GET /api/v1/topology. Manager voll
#         (inkl. Audit-abgeleiteter MCP-Aktivität); Schichtleiter nur Verbindungs-
#         status (kein Audit-Bezug); Werker/Techniker 403.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, status

from foreman.api.deps import CurrentUser, SessionDep, SubstrateClientDep
from foreman.mcp.auth import get_mcp_settings
from foreman.realtime.authz import ROLE_MANAGER, ROLE_SHIFT_LEAD
from foreman.topology.schemas import TopologyView
from foreman.topology.service import build_topology

router = APIRouter(prefix="/topology", tags=["topology"])

# Volle Sicht (inkl. Audit-abgeleiteter MCP-Aktivität): nur Manager. (Die Studie §4I
# nennt „Manager/Admin"; FOREMAN kennt keine separate admin-Rolle → durchgesetzt für manager.)
_FULL_ROLES = frozenset({ROLE_MANAGER})
# Nur Verbindungsstatus (kein Audit): zusätzlich Schichtleiter.
_STATUS_ROLES = frozenset({ROLE_MANAGER, ROLE_SHIFT_LEAD})


@router.get("", response_model=TopologyView)
async def get_topology(
    session: SessionDep,
    user: CurrentUser,
    substrate_client: SubstrateClientDep,
    probe: bool = Query(default=True, description="Substrat live proben (schreibt Smoke-Marker)."),
    fresh_within_minutes: int = Query(default=60, ge=1, le=10080),
) -> TopologyView:
    """Systemtopologie (ehrlich abgeleitet). Manager voll · Schichtleiter nur Status · sonst 403."""
    if user.role not in _STATUS_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Kein Zugriff auf die Systemtopologie"
        )
    return await build_topology(
        session,
        substrate_client=substrate_client,
        mcp_token_configured=get_mcp_settings().token is not None,
        fresh_window=timedelta(minutes=fresh_within_minutes),
        probe_substrate=probe,
        # Schichtleiter: kein Audit-Bezug → MCP-Knoten ohne Audit-Details, nur Status.
        include_audit=user.role in _FULL_ROLES,
    )
