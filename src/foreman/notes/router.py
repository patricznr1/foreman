# ============================================================
#  FOREMAN — notes/router.py
#  Zweck: Read-only HTTP-Route der Archiv-Notiz-Suche (F-SEM, Paket 1a)
#         unter GET /api/v1/worker_notes/search — hybrid: deutscher Volltext +
#         Vektor, per RRF fusioniert, mit Relevanz-Cutoff gegen vages Auffüllen.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Auth-pflichtig (alle
#         /api/v1-Routen liegen hinter der AuthMiddleware; zusätzlich ein
#         authentifizierter Operator). KEINE Schreibwirkung — reine Suche.
#  Routen-Reihenfolge: in main.py VOR dem worker_notes-CRUD-Router gemountet, damit
#         `/worker_notes/search` nicht von `/worker_notes/{note_id}` gefangen wird.
#  Verfügbarkeit: ein Embedding-Backend-Ausfall ergibt KEIN 503 mehr — der
#         Volltext-Zweig trägt allein weiter (graceful degradation, §15.4). Das
#         Archiv funktioniert auch ohne Embedding-Backend (Standalone-Argument).
#  Vertrag (kompatibel): flache `list[WorkerNoteRead]`, Reihenfolge = Relevanz
#         (RRF-Rang), KEIN Score-Feld. Sektion H (FE) liest die Position als Rang —
#         läuft ohne Frontend-Änderung weiter (FE-Trennung erst Paket 1c).
#  Datenschutz (§8): Antwort über WorkerNoteRead (ohne Vektor); keine PII/keine
#         Query/Vektoren in Logs.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Query

from foreman.api.deps import CurrentUser, EmbeddingProviderDep, SessionDep, SettingsDep
from foreman.db.models import WorkerNote
from foreman.notes.search import DEFAULT_SEARCH_K, embed_and_search_hybrid
from foreman.schemas.resources import WorkerNoteRead

router = APIRouter(prefix="/worker_notes", tags=["worker_notes_search"])


@router.get("/search", response_model=list[WorkerNoteRead])
async def search_worker_notes(
    session: SessionDep,
    provider: EmbeddingProviderDep,
    settings: SettingsDep,
    current_user: CurrentUser,
    q: str = Query(min_length=1, description="Such-Anfrage (Freitext)."),
    machine_id: int | None = Query(default=None, description="Optionaler Maschinen-Filter."),
    k: int = Query(default=DEFAULT_SEARCH_K, ge=1, le=50, description="Maximale Trefferzahl."),
) -> Sequence[WorkerNote]:
    """Archiv-Suche über die abgelegten Schichtberichte (read-only).

    Durchsucht die Berichte zugleich nach Wortlaut und nach Bedeutung und filtert
    Unzusammenhängendes heraus; die Reihenfolge ist die Relevanz. Ist die
    Bedeutungs-Suche vorübergehend nicht verfügbar, liefert die Wortlaut-Suche
    allein weiter (kein Fehler); findet auch sie nichts, ist die Liste leer.
    """
    return await embed_and_search_hybrid(
        provider,
        session,
        q,
        machine_id=machine_id,
        k=k,
        max_distance=settings.archive_vector_max_distance,
    )
