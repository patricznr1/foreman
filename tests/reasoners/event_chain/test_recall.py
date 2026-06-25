# ============================================================
#  FOREMAN — tests/reasoners/event_chain/test_recall.py
#  Zweck: NEXUS-Recall (F6, Baustein 2) — Query-Bildung aus dem Anker-Muster,
#         defensives Mapping der Substrat-Antwort, und vor allem das best-effort-
#         Verhalten: kein Substrat / Substrat-Ausfall blockiert nie. Der reale
#         SubstrateClient wird mit httpx.MockTransport getrieben (kein Netz).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from foreman.db.models import Alarm, Machine
from foreman.reasoners.event_chain.recall import (
    build_recall_query,
    map_recall_response,
    recall_similar_incidents,
)
from foreman.substrate.client import SubstrateClient


def _anchor() -> Alarm:
    return Alarm(
        id=1,
        machine_id=1,
        severity="warning",
        category="process",
        code="DRIFT",
        raised_at=datetime(2026, 6, 14, tzinfo=UTC),
    )


def _substrate(handler: httpx.MockTransport) -> SubstrateClient:
    client = httpx.AsyncClient(transport=handler, base_url="http://substrate")
    return SubstrateClient(base_url="http://substrate", client=client)


# --- Query-Bildung ---
def test_build_recall_query_enthaelt_anker_merkmale() -> None:
    machine = Machine(id=1, label="CNC-1", machine_class="cnc")
    query = build_recall_query(_anchor(), machine)
    assert "cnc" in query
    assert "DRIFT" in query
    assert "process" in query


def test_build_recall_query_ohne_merkmale_ist_generisch() -> None:
    bare = Alarm(
        id=2,
        machine_id=1,
        severity="info",
        category="",
        code=None,
        raised_at=datetime(2026, 6, 14, tzinfo=UTC),
    )
    query = build_recall_query(bare, None)
    assert "ähnlicher Vorfall" in query


# --- Mapping (rein) ---
def test_map_recall_response_results_liste() -> None:
    data = {"results": [{"content": "Lager getauscht", "id": "m1"}, "Spindel heiß"]}
    items = map_recall_response(data, max_results=5)
    assert len(items) == 2
    assert items[0].content == "Lager getauscht"
    assert items[0].ref == "m1"
    assert items[1].content == "Spindel heiß"
    assert items[1].ref is None


def test_map_recall_response_erkennt_result_als_referenz() -> None:
    # recall nutzt jetzt die kanonische extract_substrate_ref → der entry-Key
    # "result" (vormals in recall.py nicht erkannt) wird als Referenz gezogen.
    data = {"results": [{"content": "Lagerschaden", "result": "r-9"}]}
    items = map_recall_response(data, max_results=5)
    assert len(items) == 1
    assert items[0].ref == "r-9"


def test_map_recall_response_kappt_auf_max_results() -> None:
    data = {"memories": [f"Vorfall {i}" for i in range(10)]}
    items = map_recall_response(data, max_results=3)
    assert len(items) == 3


def test_map_recall_response_ohne_liste_leer() -> None:
    assert map_recall_response({"status": "ok"}, max_results=5) == []


def test_map_recall_response_ueberspringt_leere_eintraege() -> None:
    data = {"results": [{"foo": "bar"}, "  ", {"text": "echt"}]}
    items = map_recall_response(data, max_results=5)
    assert len(items) == 1
    assert items[0].content == "echt"


# --- best-effort ---
async def test_recall_ohne_substrat_leer() -> None:
    assert await recall_similar_incidents(None, "query") == []


async def test_recall_erfolgreich_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"content": "Damals: Lager"}]})

    substrate = _substrate(httpx.MockTransport(handler))
    items = await recall_similar_incidents(substrate, "query", max_results=5)
    assert len(items) == 1
    assert items[0].content == "Damals: Lager"


async def test_recall_bei_substrat_ausfall_blockiert_nicht() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "down"})

    substrate = _substrate(httpx.MockTransport(handler))
    # Darf NICHT werfen — best-effort: Ausfall → leere Liste.
    items = await recall_similar_incidents(substrate, "query")
    assert items == []
