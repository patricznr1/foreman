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
        _erinnerung(id="aaaaaaaa-0000-0000-0000-000000000001", metadata={"machine_id": 3}),
        _erinnerung(
            id="aaaaaaaa-0000-0000-0000-000000000002",
            metadata={"machine_id": 7},
            content="Anderer Vorfall",
        ),
    )

    treffer = await _nur_gedaechtnis(substrate, machine_id=3)

    assert len(treffer) == 1
    assert treffer[0].machine_id == 3


async def test_erinnerung_ohne_maschine_faellt_bei_gesetztem_filter_heraus() -> None:
    """Lieber ein Treffer zu wenig als einer, der eine Zugehörigkeit behauptet."""
    substrate = _mit_treffern(_erinnerung(metadata={}))

    assert await _nur_gedaechtnis(substrate, machine_id=3) == []


async def test_ohne_filter_bleiben_alle() -> None:
    """Die beiden Kennungen sind ausdrücklich VERSCHIEDEN.

    Die Fusion führt seit dem 27.08.2026 auf den Vorgang zusammen; zwei Treffer
    mit derselben Substrat-Kennung sind dieselbe Erinnerung, zweimal geliefert,
    und belegen einen Platz. Die Vorlage prägte vorher beide mit DERSELBEN
    Kennung — zwei Erinnerungen, die es so nicht geben kann. Solange die
    Zusammenführung fehlte, fiel das nicht auf.
    """
    substrate = _mit_treffern(
        _erinnerung(id="bbbbbbbb-0000-0000-0000-000000000001", metadata={"machine_id": 3}),
        _erinnerung(
            id="bbbbbbbb-0000-0000-0000-000000000002", metadata={}, content="ohne Maschine"
        ),
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


# Dass eine Erinnerung auf Rang 1 vor einem eigenen Treffer auf Rang 2 steht,
# prueft jetzt tests/archive/test_fusion.py gegen die Fusion selbst statt gegen
# einen Sortierschluessel, den es so nicht mehr gibt.


def test_antwortform_der_fassade_ist_die_gepinnte() -> None:
    """Die Testdaten stammen aus einem echten Abruf (20.08.2026), nicht aus einer
    selbst gebauten Beispielform — sonst prüft der Test seine eigene Erfindung."""
    roh = _erinnerung()
    assert set(roh) >= {"id", "content", "relevance", "occurred_at", "metadata"}
    assert json.loads(json.dumps(roh)) == roh


# ------------------------------------------------------------
#  Vertrag über die Sprachgrenze (Backend ↔ Anzeige)
# ------------------------------------------------------------
def test_anzeige_kennt_dieselben_quelltypen_wie_der_vertrag() -> None:
    """Die Sprachgrenze ist die Stelle, an der die beiden Listen auseinanderlaufen.

    Der Backend-Vertrag ist Python, die Anzeige TypeScript — kein Übersetzer und
    keine Prüfung der Antwort (Zod ist für diesen Endpunkt nicht verdrahtet,
    Stand 20.08.2026) hält sie zusammen. Kommt hinten ein fünfter Quelltyp dazu,
    merkt es die Anzeige erst, wenn ein Treffer ohne Beschriftung erscheint.

    Geprüft wird die AUSFÜHRBARE Form — die Typ-Definition und die beiden
    Abbildungen —, nicht ein Kommentar, der sie beschreibt.
    """
    import re
    from pathlib import Path

    from foreman.archive.schemas import SourceType

    wurzel = Path(__file__).resolve().parents[2]
    typen_datei = (wurzel / "frontend/lib/memory/types.ts").read_text(encoding="utf-8")
    quelle_datei = (wurzel / "frontend/lib/memory/source.ts").read_text(encoding="utf-8")
    vertrag_datei = (wurzel / "frontend/lib/api/contracts.ts").read_text(encoding="utf-8")

    erwartet = set(SourceType.__args__)  # type: ignore[attr-defined]

    def literale(text: str, name: str) -> set[str]:
        treffer = re.search(rf"export type {name} =([^;]+);", text)
        assert treffer, f"{name} nicht gefunden"
        return set(re.findall(r'"([a-z_]+)"', treffer.group(1)))

    assert literale(typen_datei, "SourceType") == erwartet
    assert literale(vertrag_datei, "ArchiveSourceType") == erwartet

    # Beide Abbildungen müssen JEDEN Typ führen — ein fehlender Schlüssel liefert
    # zur Laufzeit `undefined` und damit einen Treffer ohne Beschriftung.
    for name in ("SOURCE_LABEL", "SOURCE_GLYPH"):
        block = re.search(rf"{name}[^=]*=\s*\{{(.*?)\}};", quelle_datei, re.S)
        assert block, f"{name} nicht gefunden"
        schluessel = set(re.findall(r"^\s*([a-z_]+):", block.group(1), re.M))
        fehlend = erwartet - schluessel
        assert not fehlend, f"{name} kennt {fehlend} nicht — diese Treffer blieben unbeschriftet"


# ------------------------------------------------------------
#  Der Rückweg auf die Quellzeile
# ------------------------------------------------------------


async def test_rueckweg_auf_die_quellzeile_kommt_im_treffer_an() -> None:
    """Ohne ihn ist ein Erinnerungs-Treffer keiner Quellzeile zuzuordnen.

    Das hat zwei Wirkungen, die wie zwei Mängel aussehen und einer sind
    (gemessen 25.08.2026, C-060): Doppelfunde zwischen `note` und `memory`
    bleiben unauflösbar, UND eine Güte-Messung kann einen solchen Treffer
    rechnerisch nie als zutreffend werten — sie hat keinen Schlüssel, gegen den
    sie ihn halten könnte.
    """
    (hit,) = await _nur_gedaechtnis(_mit_treffern(_erinnerung()))

    assert hit.detail["quelle"] == {"art": "maintenance", "id": 4711}


async def test_die_herkunft_bleibt_memory_trotz_rueckweg() -> None:
    """AUFBAU-KONTROLLE: Der Rückweg sagt, WORAUF sich die Erinnerung bezieht —
    nicht, WAS sie ist.

    Als `maintenance` ausgegeben wäre sie eine Behauptung über die eigene
    Datenlage, die nicht stimmt: Die Wartungszeile wurde nie befragt, nur ihre
    Spiegelung. Genau das schliesst „Eigener Quelltyp, keine Tarnung" aus
    (§15.10). Ohne diesen Test liesse sich der Rückweg später bequem in
    `source_type`/`id` schreiben, und die Herkunft verschwände.
    """
    (hit,) = await _nur_gedaechtnis(_mit_treffern(_erinnerung()))

    assert hit.source_type == "memory"
    assert hit.id == 0
    assert hit.detail["herkunft"] == "gedaechtnis"


async def test_altbestand_ohne_rueckweg_bekommt_keinen_erfundenen() -> None:
    """Zeilen aus der Zeit vor der Notiz-Spiegelung tragen die Felder nicht.

    Dann fehlt der Eintrag ganz, statt mit einer geratenen Zahl gefüllt zu
    werden — eine falsche Zuordnung wäre schlimmer als eine fehlende: Sie
    schriebe einer Erinnerung eine fremde Quellzeile zu, und niemand könnte das
    später auseinanderhalten.
    """
    (hit,) = await _nur_gedaechtnis(_mit_treffern(_erinnerung(metadata={"machine_id": 3})))

    assert "quelle" not in hit.detail
    assert hit.detail["herkunft"] == "gedaechtnis"


@pytest.mark.parametrize(
    "unvollstaendig",
    [
        {"machine_id": 3, "source_type": "maintenance"},  # Kennung fehlt
        {"machine_id": 3, "source_id": 4711},  # Art fehlt
        {"machine_id": 3, "source_type": "maintenance", "source_id": 0},  # Kennung unbrauchbar
        {"machine_id": 3, "source_type": "", "source_id": 4711},  # Art leer
    ],
)
async def test_halber_rueckweg_wird_nicht_ausgeliefert(unvollstaendig: dict[str, Any]) -> None:
    """Ein Rückweg aus einer Hälfte führt nirgendwohin.

    Aufbau-Kontrolle zum Fall darüber: Ohne sie bliebe offen, ob wirklich BEIDE
    Felder verlangt werden. Eine Art ohne Kennung zeigt auf eine ganze Tabelle,
    eine Kennung ohne Art auf eine Zahl ohne Bezug.
    """
    (hit,) = await _nur_gedaechtnis(_mit_treffern(_erinnerung(metadata=unvollstaendig)))

    assert "quelle" not in hit.detail


# ------------------------------------------------------------
#  Doppelfunde: verschoben nach tests/archive/test_fusion.py
# ------------------------------------------------------------
# Seit dem 27.08.2026 entfernt die Suche Doppelfunde nicht mehr, sondern
# fuehrt sie auf den VORGANG zusammen und verrechnet ihre Raenge. Damit ist
# es keine Frage der Substrat-Veredelung mehr, sondern der Fusion ueber alle
# vier Quellen — jede frueher hier stehende Zusicherung steht dort in ihrer
# neuen Form, eine davon mit geaendertem Ergebnis.
