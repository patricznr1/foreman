# ============================================================
#  FOREMAN — tests/reasoners/test_substrat_recall_metrik.py
#  Zweck: Die vier Ausgänge des Substrat-Recalls sind unterscheidbar
#         (Freigabe-Bedingung 6 der NEXUS-Veredelung).
#  Warum eigene Datei: die Zusicherung gilt für BEIDE Konsumenten
#         (Ereignisketten- und Empfehlungs-Reasoner) — sie gehört nicht in
#         die Testdatei nur eines der beiden.
# ============================================================
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from foreman.observability.metrics import (
    RECALL_AUSGAENGE,
    RECALL_FEHLER,
    RECALL_LEER,
    RECALL_NICHT_KONFIGURIERT,
    RECALL_TREFFER,
    REGISTRY,
    record_event_chain_recall,
    record_failure_recommendation_recall,
)
from foreman.reasoners.event_chain.recall import recall_similar_incidents
from foreman.reasoners.failure.recall import recall_similar_runups
from foreman.substrate.client import SubstrateClient

_METRIKEN = {
    "event_chain": "foreman_event_chain_recall_total",
    "failure": "foreman_failure_recommendation_recall_total",
}


def _stand(metrik: str, ausgang: str) -> float:
    """Liest den aktuellen Zählerstand aus der echten Registry."""
    wert = REGISTRY.get_sample_value(metrik, {"result": ausgang})
    return float(wert or 0.0)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> SubstrateClient:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://substrat.test"
    )
    return SubstrateClient(base_url="http://substrat.test", token="t", client=http)


async def _fahre(konsument: str, substrat: SubstrateClient | None) -> Any:
    if konsument == "event_chain":
        return await recall_similar_incidents(substrat, "abfrage", max_results=3)
    return await recall_similar_runups(substrat, "abfrage", max_results=3)


@pytest.mark.parametrize("konsument", sorted(_METRIKEN))
async def test_nicht_konfiguriert_ist_ein_eigener_ausgang(konsument: str) -> None:
    metrik = _METRIKEN[konsument]
    vorher = _stand(metrik, RECALL_NICHT_KONFIGURIERT)
    leer_vorher = _stand(metrik, RECALL_LEER)

    assert await _fahre(konsument, None) == []

    assert _stand(metrik, RECALL_NICHT_KONFIGURIERT) == vorher + 1
    # Der springende Punkt: "gar nicht angebunden" darf NICHT als "nichts
    # gefunden" durchgehen — sonst sieht ein abgeschaltetes Substrat aus wie
    # ein leeres Gedächtnis.
    assert _stand(metrik, RECALL_LEER) == leer_vorher


@pytest.mark.parametrize("konsument", sorted(_METRIKEN))
async def test_treffer_und_leer_sind_getrennt(konsument: str) -> None:
    metrik = _METRIKEN[konsument]
    treffer_vorher = _stand(metrik, RECALL_TREFFER)
    leer_vorher = _stand(metrik, RECALL_LEER)

    voll = _client(lambda _r: httpx.Response(200, json={"results": [{"content": "etwas"}]}))
    assert len(await _fahre(konsument, voll)) == 1
    assert _stand(metrik, RECALL_TREFFER) == treffer_vorher + 1

    leer = _client(lambda _r: httpx.Response(200, json={"results": []}))
    assert await _fahre(konsument, leer) == []
    assert _stand(metrik, RECALL_LEER) == leer_vorher + 1
    assert _stand(metrik, RECALL_TREFFER) == treffer_vorher + 1  # unverändert


@pytest.mark.parametrize("konsument", sorted(_METRIKEN))
async def test_fehler_ist_kein_leerer_treffer(konsument: str) -> None:
    """Der Fall, der ohne Trennung unsichtbar bleibt.

    Ein Netzfehler liefert dieselbe leere Liste wie ein leeres Gedächtnis. Ginge
    er als `miss` in die Zählung, sähe eine kaputte Anbindung aus wie ein
    Gedächtnis ohne passende Erinnerung — und niemand suchte nach der Ursache.
    """
    metrik = _METRIKEN[konsument]
    fehler_vorher = _stand(metrik, RECALL_FEHLER)
    leer_vorher = _stand(metrik, RECALL_LEER)

    kaputt = _client(lambda _r: httpx.Response(500, json={"detail": "kaputt"}))
    assert await _fahre(konsument, kaputt) == []

    assert _stand(metrik, RECALL_FEHLER) == fehler_vorher + 1
    assert _stand(metrik, RECALL_LEER) == leer_vorher


@pytest.mark.parametrize("konsument", sorted(_METRIKEN))
async def test_unbrauchbare_antwortform_zaehlt_als_fehler(konsument: str) -> None:
    """Das Mapping liegt INNERHALB des try — eine Liste statt eines Objekts ist
    ein Fehler des Substrats, kein leeres Ergebnis."""
    metrik = _METRIKEN[konsument]
    fehler_vorher = _stand(metrik, RECALL_FEHLER)

    unsinn = _client(lambda _r: httpx.Response(200, text="kein json"))
    assert await _fahre(konsument, unsinn) == []
    assert _stand(metrik, RECALL_FEHLER) == fehler_vorher + 1


def test_unbekannter_ausgang_wird_abgewiesen() -> None:
    """Ein Tippfehler legte sonst still eine neue Zeitreihe an, die niemand sucht."""
    for zaehler in (record_event_chain_recall, record_failure_recommendation_recall):
        with pytest.raises(ValueError, match="Unbekannter Recall-Ausgang"):
            zaehler("hitt")


def test_alle_vier_ausgaenge_sind_erreichbar() -> None:
    """Gegen stilles Auseinanderlaufen: die Menge in der Metrik und die vier
    hier geprüften Fälle müssen dieselben sein."""
    assert RECALL_AUSGAENGE == {
        RECALL_TREFFER,
        RECALL_LEER,
        RECALL_NICHT_KONFIGURIERT,
        RECALL_FEHLER,
    }
