# ============================================================
#  FOREMAN — api/routers/me.py
#  Zweck: GET /api/v1/me — Identität, Rolle und Per-User-Scope des eingeloggten
#         Nutzers. Ermöglicht dem Frontend das Rollen-Routing (Matrix 3.1) als
#         Spiegel der Server-Autorisierung (§20.4), nicht als Ersatz dafür.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Read-only, keine Aktorik,
#         auth-pflichtig (nicht in der Open-Path-Whitelist der AuthMiddleware).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from fastapi import APIRouter

from foreman.api.deps import CurrentUser
from foreman.schemas.auth import CurrentUserRead

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=CurrentUserRead)
async def read_current_user(user: CurrentUser) -> CurrentUserRead:
    """Liefert Identität + Rolle + Per-User-Scope des eingeloggten Nutzers.

    Das Frontend spiegelt damit die Backend-Autorisierung (Rollenmatrix 3.1,
    `assigned_line_ids`/`assigned_machine_ids`); die Sichtbarkeit bleibt ≤ dem,
    was der Server tatsächlich freigibt (default-deny in `can_subscribe`).
    """
    return CurrentUserRead.model_validate(user)
