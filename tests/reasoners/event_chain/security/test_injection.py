# ============================================================
#  FOREMAN — tests/reasoners/event_chain/security/test_injection.py
#  Zweck: RED-TEAM SCHARF (Kern-Akzeptanz F6) — die echten worker_notes-Injection-
#         Payloads aus dem F-LLM-Harness gegen die ECHTE Reasoner-Pipeline. Geprüft
#         wird die Defense-in-Depth (Schutz-Doc §5.1):
#         (1) Spotlighting hält — jede Notiz geht datamarkiert als Daten rein, nie
#             als Instruktion (Mechanik-Kriterium).
#         (2) Output-Guard greift — erfundene Quellen + unbelegte Zahlen werden
#             geflaggt; referenzierte Quellen bleiben auf die Whitelist begrenzt;
#             das ReasonerExplanation-Schema validiert.
#         (3) Inertheit — der Reasoner schaltet/alarmiert nichts (keine Aktorik);
#             die Erzählung wird output-sanitisiert (LLM05).
#  Wiederverwendung: INJECTION_PAYLOADS / NUMERIC_FORGERY_PAYLOADS / build_worker_note
#         aus tests/llm/security/redteam_harness.py (Brief §2.7).
# ============================================================
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import Alarm, Machine, WorkerNote
from foreman.llm import LiteLLMGateway
from foreman.llm.grounding import build_spotlighted_messages
from foreman.reasoners.event_chain.chain import reconstruct_chain
from foreman.reasoners.event_chain.grounding_sources import build_grounding_sources
from foreman.reasoners.event_chain.prompts import EVENT_CHAIN_SYSTEM_PROMPT
from foreman.reasoners.event_chain.schema import ChainWindow
from foreman.reasoners.event_chain.service import EventChainService

# Harness aus F-LLM wiederverwenden (Top-Level-Paket `llm` unter tests/).
from llm.security.redteam_harness import (  # type: ignore[import-not-found]
    INJECTION_PAYLOADS,
    build_worker_note,
)

_T = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)
_IDS = [p[1] for p in INJECTION_PAYLOADS]


# ----------------------------------------------------------------
#  (1) Spotlighting hält — Mechanik je Payload (rein, ohne DB)
# ----------------------------------------------------------------
@pytest.mark.parametrize("payload,label", INJECTION_PAYLOADS, ids=_IDS)
def test_spotlighting_haelt_jede_injektion(payload: str, label: str) -> None:
    note_text = build_worker_note(payload)
    anchor = Alarm(
        id=1,
        machine_id=1,
        severity="warning",
        category="process",
        code="DRIFT",
        raised_at=_T,
    )
    note = WorkerNote(id=1, machine_id=1, text=note_text, created_at=_T - timedelta(hours=1))
    chain = reconstruct_chain(
        anchor=anchor,
        window=ChainWindow(start=_T - timedelta(days=7), end=_T),
        worker_notes=[note],
    )
    sources = build_grounding_sources(chain)
    # Die Notiz-Quelle ist untrusted — die zentrale Invariante.
    note_source = next(s for s in sources if s.source_id == "note:1")
    assert note_source.trusted is False

    messages = build_spotlighted_messages(EVENT_CHAIN_SYSTEM_PROMPT, sources)
    system, user = messages[0]["content"], messages[-1]["content"]
    # System-Instruktion grenzt Freitext als reine Daten ab (Instruction Hierarchy).
    assert "NIEMALS eine Anweisung" in system
    # Datamarking: Roh-Freitext steht NICHT 1:1 im Prompt; untrusted Block abgegrenzt.
    assert note_text not in user
    assert "▁" in user
    assert "FREITEXT" in user
    # Strukturierter Anker liegt getrennt im vertrauenswürdigen DATEN-Block.
    assert "[alarm:1]" in user


# ----------------------------------------------------------------
#  Helfer: Seed Anker + (bösartige) Notiz in die echte DB
# ----------------------------------------------------------------
async def _seed(session: AsyncSession, note_text: str) -> tuple[Alarm, WorkerNote]:
    machine = Machine(label="CNC-1", machine_class="cnc")
    session.add(machine)
    await session.flush()
    anchor = Alarm(
        machine_id=machine.id,
        severity="warning",
        category="process",
        code="DRIFT",
        message="Drift erkannt",
        raised_at=_T,
    )
    note = WorkerNote(machine_id=machine.id, text=note_text, created_at=_T - timedelta(hours=1))
    session.add_all([anchor, note])
    await session.flush()
    return anchor, note


# ----------------------------------------------------------------
#  (2)+(3) Volle Pipeline mit kompromittiertem Modell je Payload
# ----------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.parametrize("payload,label", INJECTION_PAYLOADS, ids=_IDS)
async def test_pipeline_neutralisiert_injektion(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
    payload: str,
    label: str,
) -> None:
    """Härtester Fall: ein Modell, das den GESAMTEN gespotlighteten Prompt 1:1
    reflektiert (echo). Selbst dann gilt: (1) der rohe Notiz-Freitext überlebt die
    Pipeline NICHT 1:1 (Datamarking greift end-to-end), (2) keine erfundene Quelle
    landet in referenced_source_ids, (3) die Erzählung ist output-sanitisiert,
    (4) der Reasoner bleibt inert (keine Aktorik), (5) das Schema validiert."""
    anchor, note = await _seed(db_session, build_worker_note(payload))
    raw_note = build_worker_note(payload)
    service = EventChainService(
        session=db_session, gateway=make_gateway(backends=[make_backend("local", echo=True)])
    )
    # Kein Crash → das ReasonerExplanation-Schema validiert trotz Injektion.
    record = await service.reconstruct(anchor.id)

    # (1) Spotlighting end-to-end: der rohe Notiz-Freitext (inkl. Payload) steht NICHT
    #     1:1 in der Erzählung — das Datamarking (Leerzeichen → ▁) hat ihn entschärft.
    assert raw_note not in record.narrative
    assert payload not in record.narrative
    # (2) Output-Guard: referenzierte Quellen bleiben strikt auf reale (whitelisted) Quellen begrenzt.
    valid = {f"alarm:{anchor.id}", f"note:{note.id}"}
    assert set(record.referenced_source_ids).issubset(valid)
    # (3) Output-Sanitisierung (LLM05): kein lebendes Script, keine rohe(n) URL/Schema in der Erzählung.
    lowered = record.narrative.lower()
    assert "<script" not in lowered
    assert "http://" not in record.narrative
    assert "javascript:" not in lowered
    # (4) Inertheit / KEINE Aktorik: der Reasoner erzeugt keinen Alarm — nur der Anker existiert.
    alarms = list(await db_session.scalars(select(Alarm)))
    assert len(alarms) == 1


# ----------------------------------------------------------------
#  Gezielte Befunde: erfundene Quelle + fabrizierte Zahl werden geflaggt
# ----------------------------------------------------------------
@pytest.mark.integration
async def test_erfundene_bracket_quelle_wird_geflaggt(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    anchor, _ = await _seed(db_session, "Lager läuft heiß")
    reply = f"Siehe [alarm:{anchor.id}] und die erfundene Quelle [evt:9999]."
    service = EventChainService(
        session=db_session, gateway=make_gateway(backends=[make_backend("local", reply=reply)])
    )
    record = await service.reconstruct(anchor.id)
    assert "evt:9999" in record.flagged_unsupported
    assert "evt:9999" not in record.referenced_source_ids
    assert record.is_hypothesis is True
    assert record.confidence == "low"


@pytest.mark.integration
async def test_fabrizierte_zahl_wird_geflaggt(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    anchor, _ = await _seed(db_session, "Lager läuft heiß")
    reply = f"Laut [alarm:{anchor.id}] lag die Temperatur bei 999 Grad."
    service = EventChainService(
        session=db_session, gateway=make_gateway(backends=[make_backend("local", reply=reply)])
    )
    record = await service.reconstruct(anchor.id)
    assert "999" in record.flagged_unsupported
    assert record.is_hypothesis is True


@pytest.mark.integration
async def test_benigne_notiz_wird_nicht_faelschlich_geflaggt(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    """False-Positive-Kontrolle: eine belegte, harmlose Erklärung bleibt sauber."""
    anchor, note = await _seed(
        db_session, "Frühschicht: Lager an Spindel läuft heiß, bitte beobachten"
    )
    reply = f"Rund um [alarm:{anchor.id}] meldete [note:{note.id}] einen Hinweis auf das Lager."
    service = EventChainService(
        session=db_session, gateway=make_gateway(backends=[make_backend("local", reply=reply)])
    )
    record = await service.reconstruct(anchor.id)
    assert record.flagged_unsupported == []
    assert record.is_hypothesis is False
    assert record.confidence == "high"
