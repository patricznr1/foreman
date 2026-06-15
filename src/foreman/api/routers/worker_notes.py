# ============================================================
#  FOREMAN — api/routers/worker_notes.py
#  Zweck: CRUD für Schichtberichte (/api/v1/worker_notes), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2).
#  Datenschutz (§8): Doppelter Schreibpfad-Schutz —
#         (1) `author` → HMAC-Token über die user_id (nie Klartext),
#         (2) `text` → NER-Maskierung (Personennamen → [PERSON]) VOR dem Insert.
#         Restrisiko bleibt; der Freitext wird nie als anonym deklariert.
#  Embedding (F-SEM, §15): der NER-maskierte Text wird beim Insert eingebettet
#         (best-effort) — Backend-Ausfall → embedding=NULL, Notiz wird trotzdem
#         geschrieben; der Backfill holt es nach. Blockiert den Insert NIE.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import EmbeddingProviderDep, PseudonymizerDep, RedactorDep, SessionDep
from foreman.db.models import WorkerNote
from foreman.embeddings import embed_best_effort
from foreman.schemas.resources import WorkerNoteCreate, WorkerNoteRead

router = APIRouter(prefix="/worker_notes", tags=["worker_notes"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=WorkerNoteRead)
async def create_worker_note(
    body: WorkerNoteCreate,
    session: SessionDep,
    pseudo: PseudonymizerDep,
    redactor: RedactorDep,
    provider: EmbeddingProviderDep,
) -> WorkerNote:
    data = body.model_dump()
    author = data.pop("author", None)
    raw_text = data.pop("text")
    # 1) Freitext VOR dem Insert maskieren. 2) Autor tokenisieren.
    masked_text = redactor.redact_person_names(raw_text)
    obj = WorkerNote(
        **data,
        text=masked_text,
        author=pseudo.tokenize_worker(author) if author else None,
    )
    # 3) Embedding beim Insert (best-effort, §15): den MASKIERTEN Text einbetten.
    vectors = await embed_best_effort(provider, [masked_text])
    if vectors is not None:
        obj.embedding = vectors[0]
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[WorkerNoteRead])
async def list_worker_notes(
    session: SessionDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[WorkerNote]:
    stmt = select(WorkerNote).order_by(WorkerNote.id.desc())
    if machine_id is not None:
        stmt = stmt.where(WorkerNote.machine_id == machine_id)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{note_id}", response_model=WorkerNoteRead)
async def get_worker_note(note_id: int, session: SessionDep) -> WorkerNote:
    obj = await session.get(WorkerNote, note_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schichtbericht nicht gefunden"
        )
    return obj
