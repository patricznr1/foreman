# ============================================================
#  FOREMAN — tests/reasoners/failure/test_recommendation_spiegelung.py
#  Zweck: Die gespiegelte Empfehlung traegt ihre ENTSTEHUNGSZEIT und das Merkmal,
#         ob das Gedaechtnis dabei zur Verfuegung stand.
#  ANLASS (02.09.2026): Beides fehlte. Ohne Zeitfeld legt der Nachlauf einen
#         Eintrag, dessen Dual-Write frueher scheiterte, mit der LAUFZEIT ab statt
#         mit seiner Entstehungszeit. Bei der Gegenstelle wird diese Zeit zur
#         Gueltigkeitszeit jedes Fakts, der aus dem Eintrag gewonnen wird — aus
#         einem Zeitfehler wird dort eine Kausalkette in falscher Reihenfolge.
#         Und ohne das Recall-Merkmal liegt eine ohne Gedaechtnis erzeugte
#         Empfehlung drueben ununterscheidbar neben einer mit vollem Kontext;
#         rueckwirkend ist das nicht zu heilen, weil die Angabe nie ankam.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, echte DB),
#         Dual-Write-Vertrag §12.4.
# ============================================================
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import FailurePredictionRecord, Machine, SemanticEvent
from foreman.llm import LiteLLMGateway
from foreman.reasoners.failure.recommendation import (
    RECOMMENDATION_EVENT_TYPE,
    RecommendationService,
)
from foreman.substrate.client import SubstrateClient
from foreman.substrate.content import baue_inhalt, ereigniszeit

pytestmark = pytest.mark.integration

_REF = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)


async def _seed_prediction(session: AsyncSession) -> FailurePredictionRecord:
    machine = Machine(label="BAZ-01", machine_class="cnc_machining_center", external_id="BAZ-01")
    session.add(machine)
    await session.flush()
    record = FailurePredictionRecord(
        machine_id=machine.id,
        reference_time=_REF,
        horizon_h=336,
        probability=0.87,
        decision_threshold=0.5,
        decision="elevated_risk",
        validation_status="simulation_only",
        data_regime="simulation",
        model_version="failure_lgbm@test",
        top_factors=[
            {
                "feature": "vibration_rms_velocity_spindle_bearing",
                "value": 3.9,
                "shap": 0.42,
                "direction": "increases_risk",
            }
        ],
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record


def _substrat_mit_treffer(machine_id: int) -> SubstrateClient:
    """Substrat-Attrappe mit einem Treffer.

    Echter Transport statt ersetzter Methoden, wie beim Ereignisketten-Reasoner:
    So laeuft der Abruf durch dieselbe Client-Schicht wie im Betrieb, und der Test
    bliebe nicht gruen, wenn sich die Abbildung der Antwort aenderte.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": f"nexus-{machine_id}",
                        "content": f"Fruehere Lagerauffaelligkeit an Maschine {machine_id}.",
                        "machine_id": machine_id,
                        "relevance": 0.7,
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://substrate")
    return SubstrateClient(base_url="http://substrate", client=client)


def _antwort(pred_id: int) -> str:
    """Ein belegter Text: 0.87 und 336 stehen beide in der trusted pred-Quelle."""
    return (
        f"[pred:{pred_id}]: Ausfallwahrscheinlichkeit 0.87 im Horizont von 336 Stunden. "
        f"Empfehlung: Lager pruefen. Simulationsbasiert, nicht validiert."
    )


async def _gespiegelte(session: AsyncSession) -> list[SemanticEvent]:
    return list(
        await session.scalars(
            select(SemanticEvent).where(SemanticEvent.event_type == RECOMMENDATION_EVENT_TYPE)
        )
    )


async def test_die_gespiegelte_empfehlung_traegt_ihre_entstehungszeit(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    """DIE NAHT zwischen Spiegel-Nutzlast und `ZEIT_FELDER`.

    Beide Haelften sind einzeln richtig und trotzdem wirkungslos, wenn der
    Schluessel nicht derselbe ist: `ereigniszeit` schlaegt ueber `.get` nach und
    liefert bei einem anderen Namen einfach `None`. Nichts wuerde rot, und der
    Nachlauf legte den Eintrag wieder mit der Laufzeit ab.
    """
    pred = await _seed_prediction(db_session)
    service = RecommendationService(
        sichtbare_maschinen=None,
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=_antwort(pred.id))]),
    )
    record = await service.recommend(pred.id)

    events = await _gespiegelte(db_session)
    assert len(events) == 1
    payload = events[0].payload

    # GELESEN, nicht erzeugt: derselbe Zeitpunkt, den die Datenbank der Zeile gab.
    assert payload["created_at"] == record.created_at.isoformat()
    # Ohne Zone weist die Gegenstelle mit 422 ab — das kostet nicht die Zeit,
    # sondern den GANZEN Eintrag.
    assert datetime.fromisoformat(payload["created_at"]).tzinfo is not None
    # Die Naht selbst.
    assert ereigniszeit(RECOMMENDATION_EVENT_TYPE, payload) == payload["created_at"]
    # Ohne Substrat entstand sie ohne historischen Kontext, und die Nutzlast sagt es.
    assert payload["recall_used"] is False


async def test_das_recall_merkmal_folgt_der_lage(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    """AUFBAU-KONTROLLE zum Fall darueber.

    Dort steht `recall_used is False` — und das bliebe auch gruen, wenn das Feld
    fest verdrahtet waere. Erst dieser Zwilling belegt, dass es der Lage folgt;
    sonst unterschiede es drueben nichts.
    """
    pred = await _seed_prediction(db_session)
    service = RecommendationService(
        sichtbare_maschinen=None,
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=_antwort(pred.id))]),
        substrate=_substrat_mit_treffer(pred.machine_id),
    )
    await service.recommend(pred.id)

    events = await _gespiegelte(db_session)
    assert len(events) == 1
    assert events[0].payload["recall_used"] is True


async def test_die_gespiegelte_empfehlung_ist_einmalig_und_nennt_die_anlage(
    db_session: AsyncSession,
    make_gateway: Callable[..., LiteLLMGateway],
    make_backend: Callable[..., object],
) -> None:
    """DIE NAHT zwischen Nutzlast und Satz (C-124) — wie bei der Ereigniskette."""
    pred = await _seed_prediction(db_session)
    service = RecommendationService(
        sichtbare_maschinen=None,
        session=db_session,
        gateway=make_gateway(backends=[make_backend("local", reply=_antwort(pred.id))]),
    )
    erste = await service.recommend(pred.id)
    zweite = await service.recommend(pred.id)

    events = await _gespiegelte(db_session)
    assert len(events) == 2
    nutzlasten = {ev.payload["source_id"]: ev.payload for ev in events}
    assert set(nutzlasten) == {erste.id, zweite.id}
    assert nutzlasten[erste.id]["machine_external_id"] == "BAZ-01"
    saetze = {baue_inhalt(RECOMMENDATION_EVENT_TYPE, p) for p in nutzlasten.values()}
    assert len(saetze) == 2, saetze
    assert all(f"an BAZ-01 (Kennung {pred.machine_id}, " in s for s in saetze), saetze
