# ============================================================
#  FOREMAN — tests/archive/test_substrat_veredelung.py
#  Zweck: Der Substrat-Strom als vierte Quelle der Archiv-Fusion.
#  Architektur-Einordnung: Freigabe-Bedingungen 4/5/6 der NEXUS-Veredelung
#         (PAKET3_BAUVORGABEN Abschnitt 9), zusammengeführt an der Stelle, an
#         der sie zusammen wirken.
#  Kein Substrat nötig: der Client läuft gegen einen MockTransport, die eigenen
#         Quellen werden nicht abgefragt (sources=("memory",)).
# ============================================================
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from foreman.archive.search import search_archive
from foreman.substrate.client import SubstrateClient


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> SubstrateClient:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://substrat.test"
    )
    return SubstrateClient(base_url="http://substrat.test", token="t", client=http)


def _mit_treffern(*treffer: dict[str, Any]) -> SubstrateClient:
    return _client(lambda _r: httpx.Response(200, json={"results": list(treffer)}))


def _erinnerung(**felder: Any) -> dict[str, Any]:
    """Ein Treffer in der Form, die die Fassade wirklich liefert (live abgenommen)."""
    grund: dict[str, Any] = {
        "id": "13205b00-0618-4c58-90e4-163a4356166a",
        "content": "Wartung (inspection) an Maschine 3 durchgeführt.",
        "relevance": 0.68,
        "source": "substrate:foreman",
        "entry_type": "observation",
        "metadata": {"machine_id": 3, "source_type": "maintenance", "source_id": 4711},
        "occurred_at": "2026-06-24T09:47:17.982308",
    }
    grund.update(felder)
    return grund


async def _nur_gedaechtnis(substrate: SubstrateClient, **kwargs: Any) -> list[Any]:
    """Fährt die Fusion mit dem Gedächtnis als EINZIGER Quelle.

    Die drei eigenen Quellen brauchen eine Datenbank; hier geht es um den vierten
    Strom, und der ist ohne sie prüfbar.
    """
    return await search_archive(
        MagicMock(),
        AsyncMock(),
        kwargs.pop("q", "Wartung"),
        sources=("memory",),
        max_distance=0.55,
        substrate=substrate,
        substrate_k=kwargs.pop("substrate_k", 5),
        **kwargs,
    )


# ------------------------------------------------------------
#  Der Treffer selbst
# ------------------------------------------------------------
async def test_erinnerung_wird_zum_archiv_treffer() -> None:
    (hit,) = await _nur_gedaechtnis(_mit_treffern(_erinnerung()))

    assert hit.source_type == "memory", "die Herkunft muss sichtbar bleiben"
    assert hit.machine_id == 3
    assert hit.timestamp == datetime(2026, 6, 24, 9, 47, 17, 982308, tzinfo=UTC)
    assert "Wartung" in hit.excerpt
    assert hit.detail["herkunft"] == "gedaechtnis"


async def test_inhalt_wird_entschaerft_nicht_nur_gekuerzt() -> None:
    """Freigabe-Bedingung 5: Der Inhalt kommt aus dem Gedächtnis zurück und ist
    untrusted. Auf dem Archiv-Pfad lief er bisher nur durch die kürzende
    Funktion — HTML und Verweise blieben stehen."""
    boesartig = "Notiz <script>alert(1)</script> siehe [hier](javascript:steal())"
    (hit,) = await _nur_gedaechtnis(_mit_treffern(_erinnerung(content=boesartig)))

    assert "<script>" not in hit.excerpt
    assert "javascript" not in hit.excerpt.lower()
    assert "steal" not in hit.excerpt
    assert "hier" in hit.excerpt, "der Linktext bleibt lesbar"


async def test_treffer_ohne_zeit_landet_hinten_statt_vorn() -> None:
    """Ein Ersatz-Zeitpunkt "jetzt" machte den ältesten Treffer zum jüngsten."""
    (hit,) = await _nur_gedaechtnis(_mit_treffern(_erinnerung(occurred_at=None)))

    assert hit.timestamp < datetime.now(UTC)
    assert hit.timestamp.year == 1970


async def test_kein_erfundener_primaerschluessel() -> None:
    """`id` ist bei den eigenen Quellen der Primärschlüssel. Eine Erinnerung hat
    keinen — eine erfundene Zahl zeigte auf eine fremde Zeile."""
    (hit,) = await _nur_gedaechtnis(_mit_treffern(_erinnerung()))

    assert hit.id == 0


# ------------------------------------------------------------
#  Maschinen-Filter
# ------------------------------------------------------------
async def test_maschinen_filter_wirkt_auch_auf_erinnerungen() -> None:
    """Bei den eigenen Quellen ist `machine_id` ein harter WHERE-Filter. Der
    Abruf ist semantisch und kennt ihn nicht — nachgefiltert wird trotzdem,
    sonst behauptete ein Treffer eine Zugehörigkeit, die niemand geprüft hat."""
    substrate = _mit_treffern(
        _erinnerung(metadata={"machine_id": 3}),
        _erinnerung(metadata={"machine_id": 7}, content="Anderer Vorfall"),
    )

    treffer = await _nur_gedaechtnis(substrate, machine_id=3)

    assert len(treffer) == 1
    assert treffer[0].machine_id == 3


async def test_erinnerung_ohne_maschine_faellt_bei_gesetztem_filter_heraus() -> None:
    """Lieber ein Treffer zu wenig als einer, der eine Zugehörigkeit behauptet."""
    substrate = _mit_treffern(_erinnerung(metadata={}))

    assert await _nur_gedaechtnis(substrate, machine_id=3) == []


async def test_ohne_filter_bleiben_alle() -> None:
    substrate = _mit_treffern(
        _erinnerung(metadata={"machine_id": 3}),
        _erinnerung(metadata={}, content="ohne Maschine"),
    )

    assert len(await _nur_gedaechtnis(substrate)) == 2


# ------------------------------------------------------------
#  Best-effort — das Archiv trägt ohne Gedächtnis weiter
# ------------------------------------------------------------
@pytest.mark.parametrize(
    "antwort",
    [
        httpx.Response(500, json={"detail": "kaputt"}),
        httpx.Response(200, text="kein json"),
        httpx.Response(200, json={"results": "keine Liste"}),
    ],
)
async def test_jeder_substrat_fehler_bleibt_folgenlos(antwort: httpx.Response) -> None:
    """Dieselbe Zusage wie für den Embedding-Ausfall (§15.8): kein 503, das
    Archiv funktioniert ohne Gedächtnis weiter."""
    treffer = await _nur_gedaechtnis(_client(lambda _r: antwort))

    assert treffer == []


async def test_ohne_client_passiert_nichts() -> None:
    treffer = await search_archive(
        MagicMock(),
        AsyncMock(),
        "Wartung",
        sources=("memory",),
        max_distance=0.55,
        substrate=None,
        substrate_k=5,
    )
    assert treffer == []


async def test_substrate_k_null_fragt_gar_nicht_erst() -> None:
    """Der Schalter wirkt über substrate_k=0 — dann darf kein Aufruf rausgehen."""
    gerufen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        gerufen.append(request.url.path)
        return httpx.Response(200, json={"results": [_erinnerung()]})

    treffer = await _nur_gedaechtnis(_client(handler), substrate_k=0)

    assert treffer == []
    assert gerufen == [], "abgeschaltet heißt: keine Anfrage, nicht nur kein Ergebnis"


async def test_gedaechtnis_nicht_gewaehlt_fragt_nicht() -> None:
    """`sources` ohne "memory" → der vierte Strom bleibt still, auch mit Client."""
    gerufen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        gerufen.append(request.url.path)
        return httpx.Response(200, json={"results": [_erinnerung()]})

    await search_archive(
        MagicMock(),
        AsyncMock(),
        "Wartung",
        sources=(),
        max_distance=0.55,
        substrate=_client(handler),
        substrate_k=5,
    )
    assert gerufen == []


# ------------------------------------------------------------
#  Der Schalter
# ------------------------------------------------------------
def test_schalter_ist_per_default_aus() -> None:
    """Ein unbekannter source_type bricht die Prüfung der Antwort im Frontend.
    Eingeschaltet wird erst, wenn beide Seiten den Typ kennen."""
    from foreman.config import Settings

    einstellungen = Settings(_env_file=None)
    assert einstellungen.archive_substrate_enabled is False


def test_abgeschalteter_schalter_reicht_keinen_client_durch() -> None:
    """Der Router entscheidet, nicht die Suche: ohne Schalter kommt gar kein
    Client an — der Strom ist dann strukturell still, nicht nur leer."""
    import inspect

    from foreman.archive import router

    quelle = inspect.getsource(router.search_archive_endpoint)
    assert "settings.archive_substrate_enabled" in quelle
    assert "substrate=substrat" in quelle


def test_gedaechtnis_gehoert_zu_den_waehlbaren_quellen() -> None:
    from foreman.archive.search import ALL_SOURCES

    assert "memory" in ALL_SOURCES


def test_erinnerungen_mischen_sich_unter_die_eigenen_treffer() -> None:
    """Die Fusion ordnet nach quelleninternem Rang — eine Erinnerung auf Rang 1
    steht damit vor einem eigenen Treffer auf Rang 2, nicht hinter allen."""
    from foreman.archive.search import _rrf_key

    rang_eins = _rrf_key((1, MagicMock(timestamp=datetime.now(UTC), source_type="memory", id=0)))
    rang_zwei = _rrf_key((2, MagicMock(timestamp=datetime.now(UTC), source_type="note", id=5)))
    assert rang_eins < rang_zwei


def test_antwortform_der_fassade_ist_die_gepinnte() -> None:
    """Die Testdaten stammen aus einem echten Abruf (20.08.2026), nicht aus einer
    selbst gebauten Beispielform — sonst prüft der Test seine eigene Erfindung."""
    roh = _erinnerung()
    assert set(roh) >= {"id", "content", "relevance", "occurred_at", "metadata"}
    assert json.loads(json.dumps(roh)) == roh
