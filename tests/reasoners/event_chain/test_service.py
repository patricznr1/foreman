# ============================================================
#  FOREMAN — tests/reasoners/event_chain/test_service.py
#  Zweck: Output-Guard (rein) + E2E-Pipeline (F6, Baustein 5/6) gegen ECHTE DB,
#         Gateway gemockt (reales LiteLLMGateway über Mock-Backend), Substrat None.
# ============================================================
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
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
from foreman.substrate.client import SubstrateClient
from foreman.substrate.content import ereigniszeit

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
        sichtbare_maschinen=None,
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=reply)]),
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
    service = EventChainService(
        sichtbare_maschinen=None, session=db_session, gateway=make_gateway()
    )
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
        sichtbare_maschinen=None,
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
        sichtbare_maschinen=None,
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=reply)]),
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
        sichtbare_maschinen=None,
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", fail=True)]),
    )
    with pytest.raises(GatewayError):
        await service.reconstruct(anchor.id)


@pytest.mark.integration
async def test_reconstruct_friert_ketten_snapshot_ein(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    """§21-D: Der persistierte Ketten-Snapshot ist eine Momentaufnahme — er wird
    NICHT neu abgeleitet, wenn sich die Quelldaten später ändern. Beweis: eine
    nachträgliche Notiz im Fenster lässt den alten Snapshot unberührt, taucht aber
    in einer NEUEN Rekonstruktion auf."""
    machine, anchor, note = await _seed(db_session)
    reply = f"Vor [alarm:{anchor.id}] meldete [note:{note.id}] einen Hinweis."
    service = EventChainService(
        sichtbare_maschinen=None,
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=reply)]),
    )
    record1 = await service.reconstruct(anchor.id)
    assert record1.chain_snapshot is not None
    assert record1.siblings_snapshot == []  # kein Substrat → kein Fake
    count1 = len(record1.chain_snapshot["events"])
    assert any(e["source_id"] == f"alarm:{anchor.id}" for e in record1.chain_snapshot["events"])

    # Quelldaten ändern sich NACH der Rekonstruktion.
    db_session.add(
        WorkerNote(
            machine_id=machine.id,
            text="Nachtrag im Fenster",
            created_at=_ANCHOR_TIME - timedelta(hours=1),
        )
    )
    await db_session.flush()

    # Der eingefrorene Snapshot bleibt unverändert ...
    assert len(record1.chain_snapshot["events"]) == count1
    # ... eine NEUE Rekonstruktion sieht die zusätzliche Notiz.
    record2 = await service.reconstruct(anchor.id)
    assert record2.chain_snapshot is not None
    assert len(record2.chain_snapshot["events"]) == count1 + 1


# ------------------------------------------------------------
#  Der Ausschnitt greift auf das, was das Gedächtnis liefert
# ------------------------------------------------------------
#  Der Recall sucht nach Maschinenklasse und Signatur, nicht nach Maschine — er
#  trifft also absichtlich gleichartige Maschinen ANDERER Linien. Die Treffer gehen
#  von dort zwei Wege: in die Schwester-Referenzen und als Grounding-Quellen ins
#  Sprachmodell. Deshalb wird direkt nach dem Abruf gefiltert und nicht erst auf dem
#  Ergebnis; für den zweiten Weg wäre das zu spät.


def _substrat_mit_treffern(*machine_ids: int) -> SubstrateClient:
    """Substrat-Stub, der je Maschine einen Treffer liefert.

    Echter Transport statt ersetzter Methoden: So läuft der Abruf durch dieselbe
    Client-Schicht wie im Betrieb, und der Test bliebe nicht grün, wenn sich die
    Abbildung der Antwort änderte.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": f"nexus-{mid}",
                        "content": f"Alarm an Maschine {mid} ausgelöst.",
                        "machine_id": mid,
                        "relevance": 0.7,
                    }
                    for mid in machine_ids
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://substrate")
    return SubstrateClient(base_url="http://substrate", client=client)


@pytest.mark.integration
async def test_fremde_erinnerungen_landen_nicht_in_der_erklaerung(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    """Ein beschränkter Auslöser bekommt keine Geschwister fremder Maschinen.

    Geprüft wird der Zustand NACH dem Lauf, nicht der Aufruf einer Funktion: Der
    Schnappschuss ist das, was persistiert wird und später wieder herauskommt.
    """
    machine, anchor, _ = await _seed(db_session)
    fremde = Machine(label="CNC-fremd", machine_class="cnc")
    db_session.add(fremde)
    await db_session.flush()

    service = EventChainService(
        sichtbare_maschinen=[machine.id],
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply="Kette rekonstruiert.")]),
        substrate=_substrat_mit_treffern(machine.id, fremde.id),
    )
    record = await service.reconstruct(anchor.id)

    gefundene = {s.get("machine_id") for s in (record.siblings_snapshot or [])}
    assert fremde.id not in gefundene, (
        f"❌ Die Erklärung trägt eine Erinnerung an die fremde Maschine {fremde.id}."
    )
    # Und der Auszugstext darf sie auch nicht nennen — dort steht die Nummer im Klartext.
    for eintrag in record.siblings_snapshot or []:
        assert f"Maschine {fremde.id}" not in str(eintrag.get("excerpt", "")), (
            "❌ Der Auszug nennt die fremde Maschine im Klartext."
        )


@pytest.mark.integration
async def test_eigene_erinnerungen_bleiben_erhalten(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    """Kontroll-Zwilling: Der Filter entfernt nicht einfach alles.

    Ohne ihn bliebe der Test darüber auch dann grün, wenn der Recall gar nicht
    ankäme — an einem Stub-Fehler, an der Abbildung, an einer leeren Antwort.
    """
    machine, anchor, _ = await _seed(db_session)

    service = EventChainService(
        sichtbare_maschinen=[machine.id],
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply="Kette rekonstruiert.")]),
        substrate=_substrat_mit_treffern(machine.id),
    )
    record = await service.reconstruct(anchor.id)

    gefundene = {s.get("machine_id") for s in (record.siblings_snapshot or [])}
    assert machine.id in gefundene, (
        "❌ Auch die eigene Erinnerung fehlt — dann sperrt der Filter alles, statt "
        f"richtig zu trennen. Schnappschuss: {record.siblings_snapshot}"
    )
    assert record.recall_used is True


@pytest.mark.integration
async def test_die_kette_schickt_eine_vorgangskennung_mit_dem_anker(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    """Der Ketten-Abruf traegt die Nummer des ANKER-ALARMS.

    Warum gegen den echten Dienst und nicht gegen die Abruf-Funktion: Zwischen
    Aufrufstelle und Leitung liegen mehrere Stationen, und die Kennung wird an
    der Aufrufstelle GEBAUT. Ein Test eine Ebene tiefer belegte nur, dass eine
    mitgegebene Kennung durchgereicht wird — nicht, dass hier ueberhaupt eine
    entsteht.

    Der Anker ist der richtige Bezug: Er ist das, worauf sich der Abruf bezieht,
    seine Nummer ist nicht personenbezogen, und die Anfrage selbst geht bewusst
    NICHT hinein — sie kann Werker-Freitext enthalten.
    """
    machine, anchor, _ = await _seed(db_session)
    # Der Lauf spricht das Substrat ZWEIMAL an: einmal fragend (recall) und am
    # Ende spiegelnd (remember, Dual-Write der fertigen Kette). Nur der Abruf
    # traegt eine Vorgangskennung — ohne die Trennung nach Pfad pruefte der Fall
    # die falsche Anfrage und waere zufaellig rot oder gruen.
    gesendet: list[tuple[str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        gesendet.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"results": []})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://substrate")
    service = EventChainService(
        sichtbare_maschinen=[machine.id],
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply="Kette rekonstruiert.")]),
        substrate=SubstrateClient(base_url="http://substrate", client=http),
    )
    await service.reconstruct(anchor.id)

    abrufe = [n for pfad, n in gesendet if "recall" in pfad]
    assert len(abrufe) == 1, (
        f"❌ Der Ketten-Lauf hat das Gedaechtnis nicht genau einmal befragt: "
        f"{[p for p, _ in gesendet]}"
    )
    kennung = abrufe[0].get("correlation_id")
    assert isinstance(kennung, str) and kennung.startswith(f"kette-{anchor.id}-"), (
        f"❌ Die Kennung nennt den Anker-Alarm {anchor.id} nicht: {kennung!r}"
    )
    # Und die Anfrage selbst darf NICHT in der Kennung stehen — sie ist der Weg,
    # auf dem Freitext versehentlich nach draussen ginge.
    assert str(abrufe[0].get("query", "")) not in kennung


@pytest.mark.integration
async def test_die_gespiegelte_kette_traegt_entstehungszeit_und_recall_merkmal(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    """DIE NAHT zwischen Spiegel-Nutzlast und `ZEIT_FELDER`.

    Beide Haelften sind einzeln richtig und trotzdem wirkungslos, wenn der
    Schluessel nicht derselbe ist: `ereigniszeit` schlaegt ueber `.get` nach und
    liefert bei einem anderen Namen einfach `None`. Nichts wuerde rot, und der
    Eintrag traege beim Nachlauf wieder die Laufzeit — genau der Fehler, gegen
    den das hier gebaut ist.
    """
    _, anchor, _ = await _seed(db_session)
    service = EventChainService(
        sichtbare_maschinen=None,
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=f"Siehe [alarm:{anchor.id}].")]),
    )
    record = await service.reconstruct(anchor.id)

    events = list(
        await db_session.scalars(
            select(SemanticEvent).where(SemanticEvent.event_type == EVENT_CHAIN_EVENT_TYPE)
        )
    )
    assert len(events) == 1
    payload = events[0].payload

    # GELESEN, nicht erzeugt: derselbe Zeitpunkt, den die Datenbank der Zeile gab.
    assert payload["created_at"] == record.created_at.isoformat()
    # Ohne Zone weist die Gegenstelle mit 422 ab — und das kostet nicht die Zeit,
    # sondern den GANZEN Eintrag.
    assert datetime.fromisoformat(payload["created_at"]).tzinfo is not None
    # Die Naht selbst.
    assert ereigniszeit(EVENT_CHAIN_EVENT_TYPE, payload) == payload["created_at"]
    # Ohne Substrat wurde blind erzaehlt, und die Nutzlast sagt es.
    assert payload["recall_used"] is False


@pytest.mark.integration
async def test_das_recall_merkmal_folgt_der_lage(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    """AUFBAU-KONTROLLE zum Fall darueber.

    Dort steht `recall_used is False` — und das bliebe auch dann gruen, wenn das
    Feld fest verdrahtet waere. Erst dieser Zwilling belegt, dass es der Lage
    folgt. Er ist der Grund, warum das Merkmal drueben ueberhaupt etwas
    unterscheidet.
    """
    _, anchor, _ = await _seed(db_session)
    service = EventChainService(
        sichtbare_maschinen=None,
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=f"Siehe [alarm:{anchor.id}].")]),
        substrate=_substrat_mit_treffern(anchor.machine_id),
    )
    record = await service.reconstruct(anchor.id)

    events = list(
        await db_session.scalars(
            select(SemanticEvent).where(SemanticEvent.event_type == EVENT_CHAIN_EVENT_TYPE)
        )
    )
    assert record.recall_used is True
    assert events[0].payload["recall_used"] is True
