# ============================================================
#  FOREMAN — api/routers/ws_ticket.py
#  Zweck: GET /api/v1/ws-ticket — prägt ein KURZLEBIGES, WS-scoped Ticket für den
#         ?token=-Query von /api/v1/ws. So muss das Frontend nicht das volle
#         Session-JWT an Browser-JS ausliefern (§21.8-Security-Follow-up).
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Read-only, keine Aktorik,
#         auth-pflichtig (nicht in der Open-Path-Whitelist der AuthMiddleware).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from fastapi import APIRouter

from foreman.api.deps import CurrentUser, SettingsDep
from foreman.core.security import DEFAULT_WS_TICKET_SECONDS, create_ws_ticket
from foreman.schemas.auth import WsTicketResponse

router = APIRouter(tags=["auth"])


@router.get("/ws-ticket", response_model=WsTicketResponse)
async def issue_ws_ticket(user: CurrentUser, settings: SettingsDep) -> WsTicketResponse:
    """Gibt ein kurzlebiges WS-Ticket (aud="ws") für den authentifizierten Nutzer aus.

    Das Ticket ist nur am WebSocket gültig (Scope-Begrenzung: HTTP-Routen lehnen es
    ab) und kurzlebig — bei Leak im Query-String/JS bleibt die Restgültigkeit klein.
    """
    ticket = create_ws_ticket(str(user.id), settings)
    return WsTicketResponse(ticket=ticket, expires_in=DEFAULT_WS_TICKET_SECONDS)
