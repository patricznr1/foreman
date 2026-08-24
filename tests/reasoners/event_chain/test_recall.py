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
import pytest

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


# ------------------------------------------------------------
#  Rangierbarkeit gegen einen ArchiveHit (Freigabe-Bedingung 4)
# ------------------------------------------------------------
def test_recall_item_uebernimmt_zeit_und_aehnlichkeit_der_fassade() -> None:
    """Die reale Antwortform der Substrate-Fassade, live abgenommen 20.08.2026.

    Der Treffer stammt wörtlich aus POST /api/substrate/recall gegen die
    betriebene Anlage — nicht aus einer selbst gebauten Beispielform.
    """
    antwort = {
        "results": [
            {
                "id": "13205b00-0618-4c58-90e4-163a4356166a",
                "content": "FOREMAN Substrat-Smoke foreman-smoke-a4639f58",
                "relevance": 0.6824336923266521,
                "source": "substrate:foreman",
                "entry_type": "observation",
                "metadata": {"kind": "smoke", "temporal_label": "vor 2 Wochen"},
                "occurred_at": "2026-07-30T13:11:47.191796",
            }
        ],
        "query": "machine note",
        "namespace": "foreman",
        "total_count": 1,
    }
    (item,) = map_recall_response(antwort, max_results=5)
    assert item.relevance == 0.6824336923266521
    assert item.occurred_at == datetime(2026, 7, 30, 13, 11, 47, 191796, tzinfo=UTC)


def test_zeitstempel_ohne_zone_wird_als_utc_gelesen() -> None:
    """Die Fassade schickt `occurred_at` OHNE Zonen-Kennung.

    Bliebe der Wert naiv, würde erst der Vergleich mit einem ArchiveHit.timestamp
    (aware) mit TypeError abbrechen — weit weg von der Ursache. Der Test hält
    fest, dass die Zone hier gesetzt wird, nicht erst beim Sortieren.
    """
    (item,) = map_recall_response(
        {"results": [{"content": "x", "occurred_at": "2026-07-30T13:11:47"}]}, max_results=1
    )
    assert item.occurred_at is not None
    assert item.occurred_at.tzinfo is not None
    # Gegen einen aware-Zeitstempel vergleichbar — das ist der Zweck des Feldes.
    assert item.occurred_at < datetime.now(UTC)


def test_zone_im_zeitstempel_bleibt_erhalten() -> None:
    (item,) = map_recall_response(
        {"results": [{"content": "x", "occurred_at": "2026-07-30T13:11:47Z"}]}, max_results=1
    )
    assert item.occurred_at == datetime(2026, 7, 30, 13, 11, 47, tzinfo=UTC)


def test_fehlende_felder_bleiben_none_statt_geraten() -> None:
    """Kein Ersatzwert. Ein Treffer ohne Rang ist ehrlich rangelos."""
    (item,) = map_recall_response({"results": [{"content": "x"}]}, max_results=1)
    assert item.relevance is None
    assert item.occurred_at is None


@pytest.mark.parametrize(
    "kaputt",
    [
        {"content": "x", "relevance": True},  # bool ist int-Subtyp, kein Rang
        {"content": "x", "relevance": "nicht-numerisch"},
        {"content": "x", "relevance": float("nan")},
        {"content": "x", "relevance": float("inf")},
    ],
)
def test_unbrauchbare_aehnlichkeit_wird_verworfen(kaputt: dict[str, object]) -> None:
    """Ein Rang, der sich nicht ordnen lässt, ist kein Rang — lieber None."""
    (item,) = map_recall_response({"results": [kaputt]}, max_results=1)
    assert item.relevance is None
    assert item.content == "x"  # der Treffer selbst überlebt


@pytest.mark.parametrize(
    "kaputt",
    [
        {"content": "x", "occurred_at": "gestern"},
        {"content": "x", "occurred_at": ""},
        {"content": "x", "occurred_at": 1753877507},  # Unix-Sekunden sind kein ISO-Format
        {"content": "x", "occurred_at": None},
    ],
)
def test_unlesbare_zeit_wird_verworfen(kaputt: dict[str, object]) -> None:
    (item,) = map_recall_response({"results": [kaputt]}, max_results=1)
    assert item.occurred_at is None
    assert item.content == "x"


def test_zeit_und_rang_auch_aus_dem_metadaten_container() -> None:
    """Dieselbe Such-Ebenen-Regel wie für machine_id — kein zweiter Weg."""
    (item,) = map_recall_response(
        {
            "results": [
                {"content": "x", "metadata": {"occurred_at": "2026-05-01T08:00:00Z", "score": 0.5}}
            ]
        },
        max_results=1,
    )
    assert item.occurred_at == datetime(2026, 5, 1, 8, 0, tzinfo=UTC)
    assert item.relevance == 0.5


# ------------------------------------------------------------
#  Datenblock-Markierung der Gegenstelle (Umstellung 24.08.2026)
# ------------------------------------------------------------


def test_datenblock_markierung_wird_abgeschaelt() -> None:
    """Der Inhalt kommt heraus, nicht die Hülle.

    ANLASS: Die Gegenstelle zeichnet zurückgegebene Inhalte als Datenblock aus,
    damit ein lesendes Modell sie nicht als Anweisung nimmt. Bisher geschah das
    nur auf ihrer Werkzeug-Schnittstelle; über den Weg, den FOREMAN benutzt,
    gingen Trefferlisten unmarkiert raus. Sobald die Gegenstelle umstellt, stünde
    die Hülle sonst im Auszug — und der Werker läse XML in seiner Trefferliste.

    FOREMAN verlässt sich für die Sicherheit weiterhin auf die EIGENE Schicht
    (`trusted=False` plus Spotlighting); die fremde Markierung wird abgeschält,
    nicht als Schutz gewertet.
    """
    from foreman.reasoners.event_chain.recall import entpacke_datenblock

    roh = (
        '<tool_result_data origin="nexus" entry_id="abc-1" tier="stable">'
        "Lager B lief warm."
        "</tool_result_data>"
    )
    assert entpacke_datenblock(roh) == "Lager B lief warm."


def test_unmarkierter_inhalt_bleibt_unveraendert() -> None:
    """Aufbau-Kontrolle: der HEUTIGE Zustand muss weiter tragen.

    Ohne diesen Zwilling wäre nicht unterscheidbar, ob die Entpackung wirkt oder
    ob sie schlicht alles durchreicht. Und er ist die Bedingung dafür, dass die
    Gegenstelle ihren Schalter umlegen kann, ohne dass hier etwas bricht: beide
    Zustände müssen gleichzeitig funktionieren.
    """
    from foreman.reasoners.event_chain.recall import entpacke_datenblock

    assert entpacke_datenblock("Lager B lief warm.") == "Lager B lief warm."


def test_maskierte_zeichen_kommen_zurueck() -> None:
    """Der Inhalt ist in der Hülle maskiert — sonst stünde '&lt;' im Auszug."""
    from foreman.reasoners.event_chain.recall import entpacke_datenblock

    roh = '<tool_result_data origin="nexus" tier="meta">Druck &lt; 3 bar &amp; Temperatur hoch</tool_result_data>'
    assert entpacke_datenblock(roh) == "Druck < 3 bar & Temperatur hoch"


def test_halbe_huelle_wird_nicht_angetastet() -> None:
    """Nur eine VOLLSTÄNDIGE Hülle wird abgeschält.

    Ein Text, der die Zeichenfolge zufällig oder böswillig nur teilweise
    enthält, bleibt unverändert — sonst liesse sich über einen halben Marker
    Inhalt abschneiden.
    """
    from foreman.reasoners.event_chain.recall import entpacke_datenblock

    roh = '<tool_result_data origin="nexus">ohne Ende'
    assert entpacke_datenblock(roh) == roh


def test_treffer_aus_der_gegenstelle_wird_entpackt() -> None:
    """Die Entpackung greift auf dem echten Weg, nicht nur in der Hilfsfunktion.

    Belegt, dass sie an der Stelle sitzt, die `RecallItem.content` füllt — und
    damit für BEIDE Konsumenten wirkt: Ereignisketten und Archiv-Suche.
    """
    from foreman.reasoners.event_chain.recall import map_recall_response

    antwort = {
        "results": [
            {
                "content": (
                    '<tool_result_data origin="nexus" entry_id="e-9" tier="plastic">'
                    "Spindel mahlte beim Hochlauf."
                    "</tool_result_data>"
                ),
                "id": "e-9",
            }
        ]
    }
    items = map_recall_response(antwort, max_results=5)
    assert len(items) == 1
    assert items[0].content == "Spindel mahlte beim Hochlauf."
    assert items[0].ref == "e-9"
