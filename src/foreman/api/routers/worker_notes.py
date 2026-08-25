# ============================================================
#  FOREMAN — api/routers/worker_notes.py
#  Zweck: CRUD für Schichtberichte (/api/v1/worker_notes), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2).
#  Datenschutz (§8): Doppelter Schreibpfad-Schutz —
#         (1) `author` → HMAC-Token über die user_id (nie Klartext),
#         (2) `text` → NER-Maskierung (Personennamen → [PERSON]) VOR dem Insert.
#         Restrisiko bleibt; der Freitext wird nie als anonym deklariert.
#  Maschinen-Scope (§20.4): jede Route führt `ResourceScopeDep` — ein Schichtbericht
#         gehört zu genau einer Maschine, und wer die Maschine nicht sehen darf,
#         sieht auch ihre Berichte nicht. Der Strich ist derselbe wie im Live-Push.
#  Identitätsbindung (§19): der Verfasser kommt aus dem Token, nicht aus dem Body
#         — die Zuschreibung folgt der Authentifizierung, nicht den Nutzdaten.
#         Unbekannte Felder ergeben 422 (`extra="forbid"`), statt still zu verfallen.
#  Embedding (F-SEM, §15): der NER-maskierte Text wird beim Insert eingebettet
#         (best-effort) — Backend-Ausfall → embedding=NULL, Notiz wird trotzdem
#         geschrieben; der Backfill holt es nach. Blockiert den Insert NIE.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import (
    CurrentUser,
    EmbeddingProviderDep,
    PseudonymizerDep,
    RedactorDep,
    ResourceScopeDep,
    SessionDep,
    SubstrateClientDep,
)
from foreman.db.models import WorkerNote
from foreman.embeddings import embed_best_effort
from foreman.ingestion.semantic import notiz_payload, record_semantic_event
from foreman.schemas.resources import WorkerNoteCreate, WorkerNoteRead

router = APIRouter(prefix="/worker_notes", tags=["worker_notes"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=WorkerNoteRead)
async def create_worker_note(
    body: WorkerNoteCreate,
    current_user: CurrentUser,
    session: SessionDep,
    pseudo: PseudonymizerDep,
    redactor: RedactorDep,
    provider: EmbeddingProviderDep,
    substrate: SubstrateClientDep,
    scope: ResourceScopeDep,
) -> WorkerNote:
    # 0) Der Bericht gehört an eine Maschine, die der Verfasser auch sehen darf.
    # Ohne diese Prüfung wäre der Schreibpfad der Weg, Freitext in einen fremden
    # Maschinenkontext einzustellen.
    if body.machine_id is not None:
        await scope.require(body.machine_id)
    data = body.model_dump()
    raw_text = data.pop("text")
    # 1) Freitext VOR dem Insert maskieren. 2) Autor aus dem TOKEN tokenisieren —
    # der Verfasser ist immer der eingeloggte Nutzer, nie ein Body-Feld.
    masked_text = redactor.redact_person_names(raw_text)
    obj = WorkerNote(
        **data,
        text=masked_text,
        author=pseudo.tokenize_worker(str(current_user.id)),
    )
    # 3) Embedding beim Insert (best-effort, §15): den MASKIERTEN Text einbetten.
    # `if vectors:` (nicht `is not None`) — eine leere Liste würde sonst bei vectors[0]
    # einen IndexError werfen und den „nie blockieren"-Insert-Pfad verletzen.
    vectors = await embed_best_effort(provider, [masked_text])
    if vectors:
        obj.embedding = vectors[0]
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    # 4) Dual-Write ans Gedächtnis (best-effort, §12.4). NACH dem flush, damit
    # `source_id` den echten Schlüssel trägt — ohne ihn hätte der Treffer im
    # Archiv keinen Rückweg zur Zeile und würde als eigenständige Erinnerung
    # gezeigt. Gespiegelt wird der MASKIERTE Text (nie das Rohfeld).
    await record_semantic_event(
        session,
        machine_id=obj.machine_id,
        event_type="worker_note",
        payload=notiz_payload(obj, masked_text),
        substrate=substrate,
    )
    return obj


@router.get("", response_model=list[WorkerNoteRead])
async def list_worker_notes(
    session: SessionDep,
    scope: ResourceScopeDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[WorkerNote]:
    """Schichtberichte im Maschinen-Ausschnitt des Anfragenden (jüngste zuerst)."""
    stmt = await scope.limit_to(
        select(WorkerNote).order_by(WorkerNote.id.desc()),
        WorkerNote.machine_id,
        machine_id=machine_id,
    )
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{note_id}", response_model=WorkerNoteRead)
async def get_worker_note(note_id: int, session: SessionDep, scope: ResourceScopeDep) -> WorkerNote:
    """Ein Schichtbericht — 404 auch dann, wenn er zu einer fremden Maschine gehört.

    Bewusst dieselbe Antwort wie für eine unbekannte Kennung: Ein 403 würde die
    Existenz der Zeile bestätigen und die Kennungen durchprobierbar machen.
    """
    obj = await session.get(WorkerNote, note_id)
    if obj is None or not await scope.can_see(obj.machine_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schichtbericht nicht gefunden"
        )
    return obj
