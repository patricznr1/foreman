# ============================================================
#  FOREMAN — tests/reasoners/event_chain/test_service.py
#  Zweck: Output-Guard (rein) + E2E-Pipeline (F6, Baustein 5/6) gegen ECHTE DB,
#         Gateway gemockt (reales LiteLLMGateway über Mock-Backend), Substrat None.
# ============================================================
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import (
    Alarm,
    Machine,
    MaintenanceEvent,
    SemanticEvent,
    WorkerNote,
)
from foreman.llm import GatewayError, GroundingReport, LiteLLMGateway
from foreman.reasoners.event_chain.schema import ReasonerExplanation
from foreman.reasoners.event_chain.service import (
    EVENT_CHAIN_EVENT_TYPE,
    AnchorNotFoundError,
    EventChainService,
    build_explanation,
    extract_citations,
    sanitize_narrative,
)

_ANCHOR_TIME = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)


# ----------------------------------------------------------------
#  Reiner Output-Guard
# ----------------------------------------------------------------
def test_extract_citations_eindeutig_und_geordnet() -> None:
    narrative = "Erst [alarm:1], dann [note:2], nochmal [alarm:1]."
    assert extract_citations(narrative) == ["alarm:1", "note:2"]


def test_sanitize_narrative_entfernt_html_url_markdown() -> None:
    raw = (
        "Hinweis ![x](http://evil.example/leak) <script>alert(1)</script> siehe http://evil.example"
    )
    cleaned = sanitize_narrative(raw)
    assert "<script>" not in cleaned
    assert "http://evil.example" not in cleaned
    assert "](http" not in cleaned


def test_sanitize_narrative_behaelt_source_zitate() -> None:
    assert "[alarm:5]" in sanitize_narrative("Zum Alarm [alarm:5] siehe Daten.")


@pytest.mark.parametrize(
    "dangerous",
    [
        "ftp://evil.example/leak",
        "javascript:alert(1)",
        "data:text/html,payload",
        "vbscript:msgbox(1)",
        "HTTPS://Evil.Example/X",  # Schema case-insensitiv
    ],
)
def test_sanitize_narrative_neutralisiert_nicht_http_schemata(dangerous: str) -> None:
    """Output-Smuggling (LLM05) auch über Nicht-HTTP-Schemata neutralisieren."""
    cleaned = sanitize_narrative(f"Hinweis {dangerous} bitte prüfen.")
    assert dangerous not in cleaned


def test_build_explanation_erfundene_quelle_wird_geflaggt() -> None:
    expl = build_explanation(
        anchor_alarm_id=1,
        machine_id=1,
        narrative="Laut [alarm:1] und der erfundenen Quelle [evt:9999] passierte X.",
        allowed=("alarm:1", "note:2"),
        grounding=None,
        recall_used=False,
    )
    assert "evt:9999" in expl.flagged_unsupported
    assert "evt:9999" not in expl.referenced_source_ids
    assert "alarm:1" in expl.referenced_source_ids
    assert expl.is_hypothesis is True
    assert expl.confidence == "low"


def test_build_explanation_unbelegte_zahl_wird_geflaggt() -> None:
    report = GroundingReport(
        checked=True, grounded=False, source_ids=("alarm:1",), unbacked=("999",)
    )
    expl = build_explanation(
        anchor_alarm_id=1,
        machine_id=1,
        narrative="Die Temperatur lag bei 999 Grad laut [alarm:1].",
        allowed=("alarm:1",),
        grounding=report,
        recall_used=False,
    )
    assert "999" in expl.flagged_unsupported
    assert expl.is_hypothesis is True
    assert expl.confidence == "low"


def test_build_explanation_benigne_hohe_konfidenz() -> None:
    report = GroundingReport(
        checked=True, grounded=True, source_ids=("alarm:1", "note:2"), unbacked=()
    )
    expl = build_explanation(
        anchor_alarm_id=1,
        machine_id=1,
        narrative="Rund um [alarm:1] meldete [note:2] einen Hinweis.",
        allowed=("alarm:1", "note:2"),
        grounding=report,
        recall_used=True,
    )
    assert expl.flagged_unsupported == ()
    assert expl.is_hypothesis is False
    assert expl.confidence == "high"
    assert set(expl.referenced_source_ids) == {"alarm:1", "note:2"}


def test_reasoner_explanation_validator_lehnt_nicht_whitelisted_ab() -> None:
    with pytest.raises(ValueError, match="Whitelist"):
        ReasonerExplanation(
            anchor_alarm_id=1,
            machine_id=1,
            narrative="x",
            allowed_source_ids=("alarm:1",),
            referenced_source_ids=("evt:9999",),  # nicht in Whitelist
            flagged_unsupported=(),
            is_hypothesis=False,
            confidence="high",
            recall_used=False,
            grounding=None,
        )


# ----------------------------------------------------------------
#  E2E-Pipeline gegen echte DB
# ----------------------------------------------------------------
async def _seed(
    session: AsyncSession, *, note_text: str = "Lager läuft heiß, bitte beobachten"
) -> tuple[Machine, Alarm, WorkerNote]:
    machine = Machine(label="CNC-1", machine_class="cnc")
    session.add(machine)
    await session.flush()
    anchor = Alarm(
        machine_id=machine.id,
        severity="warning",
        category="process",
        code="DRIFT",
        message="Verhaltens-Drift erkannt",
        raised_at=_ANCHOR_TIME,
    )
    note = WorkerNote(
        machine_id=machine.id,
        shift="frueh",
        text=note_text,
        created_at=_ANCHOR_TIME - timedelta(hours=2),
    )
    maintenance = MaintenanceEvent(
        machine_id=machine.id,
        type="inspection",
        performed_at=_ANCHOR_TIME - timedelta(hours=20),
    )
    session.add_all([anchor, note, maintenance])
    await session.flush()
    return machine, anchor, note


@pytest.mark.integration
async def test_reconstruct_persistiert_erklaerung(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    _, anchor, note = await _seed(db_session)
    reply = f"Vor dem Alarm [alarm:{anchor.id}] meldete die Notiz [note:{note.id}] einen Hinweis."
    service = EventChainService(
        session=db_session, gateway=make_gateway(backends=[make_backend("local", reply=reply)])
    )
    record = await service.reconstruct(anchor.id)

    assert record.id is not None
    assert record.anchor_alarm_id == anchor.id
    assert record.reasoner == "event_chain"
    assert f"alarm:{anchor.id}" in record.referenced_source_ids
    assert f"note:{note.id}" in record.referenced_source_ids
    assert record.flagged_unsupported == []
    assert record.is_hypothesis is False
    assert record.confidence == "high"
    assert record.recall_used is False


@pytest.mark.integration
async def test_reconstruct_unbekannter_anker_wirft(
    db_session: AsyncSession, make_gateway: Callable[..., LiteLLMGateway]
) -> None:
    service = EventChainService(session=db_session, gateway=make_gateway())
    with pytest.raises(AnchorNotFoundError):
        await service.reconstruct(999_999)


@pytest.mark.integration
async def test_reconstruct_spiegelt_semantic_event(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    _, anchor, _ = await _seed(db_session)
    service = EventChainService(
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=f"Siehe [alarm:{anchor.id}].")]),
    )
    await service.reconstruct(anchor.id)

    events = list(
        await db_session.scalars(
            select(SemanticEvent).where(SemanticEvent.event_type == EVENT_CHAIN_EVENT_TYPE)
        )
    )
    assert len(events) == 1
    assert events[0].machine_id == anchor.machine_id
    assert events[0].substrate_ref is None  # kein Substrat → best-effort NULL
    assert events[0].payload["reasoner"] == "event_chain"


@pytest.mark.integration
async def test_reconstruct_note_ausserhalb_fenster_nicht_referenziert(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    machine, anchor, _ = await _seed(db_session)
    # Eine sehr alte Notiz (außerhalb des Default-Fensters von 7 Tagen).
    old_note = WorkerNote(
        machine_id=machine.id,
        text="uralt",
        created_at=_ANCHOR_TIME - timedelta(days=60),
    )
    db_session.add(old_note)
    await db_session.flush()
    reply = f"Nur [alarm:{anchor.id}] und [note:{old_note.id}] erwähnt."
    service = EventChainService(
        session=db_session, gateway=make_gateway(backends=[make_backend("local", reply=reply)])
    )
    record = await service.reconstruct(anchor.id)
    # Die alte Notiz ist KEINE gültige Quelle → ihr Zitat wird geflaggt, nicht referenziert.
    assert f"note:{old_note.id}" not in record.referenced_source_ids
    assert f"note:{old_note.id}" in record.flagged_unsupported


@pytest.mark.integration
async def test_reconstruct_gateway_fehler_propagiert(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    """Ein Backend-/Gateway-Ausfall wird als GatewayError nach oben gereicht
    (und als Reasoner-Fehler in den Metriken gezählt) — nicht verschluckt."""
    _, anchor, _ = await _seed(db_session)
    service = EventChainService(
        session=db_session, gateway=make_gateway(backends=[make_backend("local", fail=True)])
    )
    with pytest.raises(GatewayError):
        await service.reconstruct(anchor.id)
