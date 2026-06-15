# ============================================================
#  FOREMAN — notes/router.py
#  Zweck: Read-only HTTP-Route der semantischen Notiz-Suche (F-SEM, Baustein 4)
#         unter GET /api/v1/worker_notes/search.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Auth-pflichtig (alle
#         /api/v1-Routen liegen hinter der AuthMiddleware; zusätzlich ein
#         authentifizierter Operator, da die Suche Embedding-Inferenz auslöst).
#         KEINE Schreibwirkung — reine Suche.
#  Routen-Reihenfolge: in main.py VOR dem worker_notes-CRUD-Router gemountet, damit
#         `/worker_notes/search` nicht von `/worker_notes/{note_id}` gefangen wird.
#  Verfügbarkeit: ein Embedding-Backend-Ausfall ergibt 503 (ehrlich) — die
#         Such-Route ist NICHT best-effort (anders als die F6-Notiz-Auswahl, §15).
#  Datenschutz (§8): Antwort über WorkerNoteRead (ohne Vektor); keine PII/keine
#         Query/Vektoren in Logs.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status

from foreman.api.deps import CurrentUser, EmbeddingProviderDep, SessionDep
from foreman.db.models import WorkerNote
from foreman.embeddings.errors import EmbeddingError
from foreman.notes.search import DEFAULT_SEARCH_K, embed_and_search
from foreman.schemas.resources import WorkerNoteRead

router = APIRouter(prefix="/worker_notes", tags=["worker_notes_search"])


@router.get("/search", response_model=list[WorkerNoteRead])
async def search_worker_notes(
    session: SessionDep,
    provider: EmbeddingProviderDep,
    current_user: CurrentUser,
    q: str = Query(min_length=1, description="Such-Anfrage (Freitext, wird eingebettet)."),
    machine_id: int | None = Query(default=None, description="Optionaler Maschinen-Filter."),
    k: int = Query(default=DEFAULT_SEARCH_K, ge=1, le=50, description="Maximale Trefferzahl."),
) -> Sequence[WorkerNote]:
    """Semantische Suche über Schichtberichte (read-only).

    Embeddet die Anfrage `q` und liefert die `k` ähnlichsten Notizen (Cosine,
    optional auf eine Maschine gefiltert). Ist das Embedding-Backend nicht
    erreichbar, antwortet die Route mit 503 (kein stilles Leer-Ergebnis)."""
    try:
        return await embed_and_search(provider, session, q, machine_id=machine_id, k=k)
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantische Suche derzeit nicht verfügbar (Embedding-Backend).",
        ) from exc
