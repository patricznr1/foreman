# ============================================================
#  FOREMAN — tests/unit/test_substrate_client.py
#  Zweck: SubstrateClient + Smoke gegen einen gemockten HTTP-Endpunkt (§9).
#  Kein echtes Substrat nötig — httpx.MockTransport simuliert die Antworten.
# ============================================================
from __future__ import annotations

import json
import logging
from collections.abc import Callable

import httpx
import pytest

from foreman.config import Settings
from foreman.substrate import client as client_modul
from foreman.substrate.client import (
    SubstrateClient,
    SubstrateError,
    SubstrateNotConfiguredError,
    SubstrateNotFoundError,
)
from foreman.substrate.smoke import run_substrate_smoke


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> SubstrateClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="http://substrate.test")
    return SubstrateClient(base_url="http://substrate.test", token="tok", client=http)


def test_internal_client_sets_bearer_header() -> None:
    client = SubstrateClient(base_url="http://substrate.test", token="geheim")
    assert client._client.headers["Authorization"] == "Bearer geheim"


async def test_remember_posts_expected_payload() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"stored": True})

    client = _make_client(handler)
    out = await client.remember("Lagergeräusch", metadata={"machine": 3})
    assert out == {"stored": True}
    assert captured["path"] == "/remember"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["content"] == "Lagergeräusch"
    assert body["namespace"] == "foreman"
    assert body["metadata"] == {"machine": 3}
    await client.aclose()


async def test_recall_posts_query() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"results": []})

    client = _make_client(handler)
    await client.recall("Vibration", max_results=3)
    assert captured["path"] == "/recall"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["query"] == "Vibration"
    assert body["max_results"] == 3
    await client.aclose()


async def test_non_dict_response_is_normalized() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2, 3])

    client = _make_client(handler)
    out = await client.reflect()
    assert out == {"result": [1, 2, 3]}
    await client.aclose()


async def test_http_error_raises_substrate_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _make_client(handler)
    with pytest.raises(SubstrateError):
        await client.remember("x")
    await client.aclose()


def test_from_settings_without_base_url_raises() -> None:
    settings = Settings(_env_file=None, substrate_base_url=None)
    with pytest.raises(SubstrateNotConfiguredError):
        SubstrateClient.from_settings(settings)


def test_from_settings_builds_client() -> None:
    settings = Settings(
        _env_file=None,
        substrate_base_url="http://substrate.test",
        substrate_token="tok",
    )
    client = SubstrateClient.from_settings(settings)
    assert isinstance(client, SubstrateClient)


def _roundtrip_handler(recall_has_marker: bool) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path == "/remember":
            return httpx.Response(200, json={"stored": True})
        if request.url.path == "/recall":
            query = body["query"]
            if recall_has_marker:
                return httpx.Response(200, json={"results": [{"content": f"echo {query}"}]})
            return httpx.Response(200, json={"results": []})
        return httpx.Response(404)

    return handler


async def test_smoke_ok_when_marker_returns() -> None:
    client = _make_client(_roundtrip_handler(recall_has_marker=True))
    result = await run_substrate_smoke(client)
    assert result.ok is True
    assert result.latency_ms >= 0
    await client.aclose()


async def test_smoke_not_ok_when_marker_missing() -> None:
    client = _make_client(_roundtrip_handler(recall_has_marker=False))
    result = await run_substrate_smoke(client)
    assert result.ok is False
    assert result.detail is not None
    await client.aclose()


async def test_smoke_not_ok_on_substrate_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _make_client(handler)
    result = await run_substrate_smoke(client)
    assert result.ok is False
    await client.aclose()


# ------------------------------------------------------------
#  Namespace-Trennung des Smoke (Freigabe-Bedingung 7)
# ------------------------------------------------------------
def _settings_with_substrate() -> Settings:
    return Settings(
        _env_file=None,
        substrate_base_url="http://substrate.test",
        substrate_token="tok",
        substrate_namespace="foreman",
        substrate_smoke_namespace="foreman-smoke",
    )


def test_from_settings_uses_operating_namespace_by_default() -> None:
    client = SubstrateClient.from_settings(_settings_with_substrate())
    assert client._namespace == "foreman"


def test_from_settings_namespace_override_wins() -> None:
    settings = _settings_with_substrate()
    client = SubstrateClient.from_settings(settings, namespace=settings.substrate_smoke_namespace)
    assert client._namespace == "foreman-smoke"


async def test_smoke_writes_into_smoke_namespace_not_the_operating_one() -> None:
    """Die Zusicherung aus §9: der Smoke verschmutzt den Abruf-Bestand nicht.

    Geprüft wird der Wert, der WIRKLICH über die Leitung geht — nicht das
    Attribut am Client. Beide Aufrufe (remember UND recall) müssen den
    Smoke-Namespace tragen; ein remember im Smoke- und ein recall im
    Betriebs-Namespace wäre genauso falsch wie umgekehrt.
    """
    settings = _settings_with_substrate()
    gesehen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        gesehen.append((request.url.path, body["namespace"]))
        if request.url.path == "/remember":
            return httpx.Response(200, json={"stored": True})
        return httpx.Response(200, json={"results": [{"content": body["query"]}]})

    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://substrate.test"
    )
    client = SubstrateClient.from_settings(
        settings, namespace=settings.substrate_smoke_namespace, client=http
    )
    await run_substrate_smoke(client)

    assert gesehen == [("/remember", "foreman-smoke"), ("/recall", "foreman-smoke")]
    assert all(ns != "foreman" for _, ns in gesehen)


def test_token_is_secret_but_reaches_the_header_in_clear() -> None:
    """SecretStr schützt Logs/Serialisierung, nicht den Aufruf selbst.

    Beide Hälften gehören zusammen: Ein Token, das nirgends mehr auftaucht,
    aber auch nicht mehr authentifiziert, wäre kein Fortschritt.
    """
    # Unverwechselbarer Wert: "tok" käme im repr schon als Teil von
    # "substrate_token" vor — der Test prüfte dann seine eigene Beschreibung
    # statt der Sache.
    geheim = "s3cr3t-substrat-4711"
    settings = Settings(
        _env_file=None,
        substrate_base_url="http://substrate.test",
        substrate_token=geheim,
    )
    assert geheim not in str(settings.substrate_token)
    assert geheim not in repr(settings)
    assert geheim not in settings.model_dump_json()
    client = SubstrateClient.from_settings(settings)
    assert client._client.headers["Authorization"] == f"Bearer {geheim}"


def test_missing_token_stays_missing() -> None:
    settings = Settings(_env_file=None, substrate_base_url="http://substrate.test")
    client = SubstrateClient.from_settings(settings)
    assert "Authorization" not in client._client.headers


def test_smoke_route_haengt_an_der_smoke_dependency() -> None:
    """Verdrahtungs-Nachweis, der OHNE Datenbank greift.

    Die Namespace-Trennung nützt nichts, wenn die Route weiter am
    Betriebs-Client hängt. Der Integrationstest dazu wird ohne Test-DB
    übersprungen — dieser hier nicht. Geprüft wird die aufgelöste
    Dependency der echten Route, nicht ein nachgebauter Aufruf.
    """
    from fastapi.routing import APIRoute

    from foreman.api.deps import get_substrate_client, get_substrate_smoke_client
    from foreman.api.routers.substrate import router

    route = next(r for r in router.routes if isinstance(r, APIRoute) and r.path.endswith("/smoke"))
    abhaengigkeiten = [d.call for d in route.dependant.dependencies]
    assert get_substrate_smoke_client in abhaengigkeiten
    assert get_substrate_client not in abhaengigkeiten


# ------------------------------------------------------------
#  forget — der Rückweg für ein Löschverlangen (Art. 17 DSGVO)
# ------------------------------------------------------------


async def test_forget_schickt_delete_auf_die_kennung() -> None:
    """Der Klient muss löschen KÖNNEN — sonst ist ein Löschverlangen nicht erfüllbar.

    ANLASS: Der Klient kannte remember, recall, reason, drift_status und reflect.
    Das Gedächtnis kann löschen (mit Entwertung der abgeleiteten Aussagen), aber
    FOREMAN hatte keinen Weg, es zu verlangen. Solange Inhalte hinausgehen, die
    auf eine Person zurückführen können, ist das eine Lücke im Löschpfad.
    """
    gesehen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["methode"] = request.method
        gesehen["pfad"] = request.url.path
        return httpx.Response(200, json={"deleted": True})

    client = _make_client(handler)
    antwort = await client.forget("abc-123")

    assert gesehen["methode"] == "DELETE"
    assert str(gesehen["pfad"]).endswith("/abc-123")
    assert antwort == {"deleted": True}


async def test_forget_meldet_einen_fehlschlag_statt_ihn_zu_verschlucken() -> None:
    """Ein misslungenes Löschen darf NICHT wie ein gelungenes aussehen.

    Aufbau-Kontrolle zum Test darüber: Ohne diese Zusicherung wäre nicht
    unterscheidbar, ob der Aufruf wirkte oder nur nicht warf — genau das
    Häkchen, das Sicherheit vortäuscht. Bei einem Löschverlangen ist die
    Erfolgsmeldung der ganze Nachweis.
    """

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "kaputt"})

    client = _make_client(handler)
    with pytest.raises(SubstrateError):
        await client.forget("abc-123")


async def test_forget_lehnt_eine_leere_kennung_ab() -> None:
    """Ohne Kennung würde der Pfad auf die Sammlung zeigen statt auf einen Eintrag.

    Ein DELETE auf die Sammlung ist im günstigen Fall ein 405 — im ungünstigen
    trifft es mehr als gemeint. Der Fehler gehört vor den Aufruf.
    """

    def handler(_request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("es darf keine Anfrage rausgehen")

    client = _make_client(handler)
    with pytest.raises(ValueError, match="Kennung"):
        await client.forget("   ")


# ------------------------------------------------------------
#  Der Weg aus der Konfiguration — nicht der von Hand gebaute
# ------------------------------------------------------------


def test_from_settings_liefert_jeden_pfad_den_der_klient_benutzt() -> None:
    """Was der Konstruktor als Vorgabe kennt, muss die Konfiguration auch liefern.

    ANLASS (Befund 25.08.2026, im Betrieb aufgeschlagen): `forget` stand im
    Vorgabewert des Konstruktors, fehlte aber in dem Verzeichnis, das
    `from_settings` baut. Ein übergebenes `paths` ERSETZT den Vorgabewert
    vollständig — im Betrieb war der Löschweg damit unerreichbar und warf
    KeyError. Auffallen konnte das nicht: Jeder Test baute seinen Klienten von
    Hand und behielt dadurch den vollständigen Vorgabewert.

    Dieser Test vergleicht deshalb die SCHLÜSSELMENGEN statt einzelner Namen —
    wer eine Methode samt Vorgabepfad hinzufügt, wird hier daran erinnert, sie
    auch aus der Konfiguration erreichbar zu machen.
    """
    aus_konfiguration = SubstrateClient.from_settings(
        Settings(substrate_base_url="https://gedaechtnis.example")
    )
    von_hand = SubstrateClient(base_url="https://gedaechtnis.example")

    assert set(aus_konfiguration._paths) == set(von_hand._paths), (
        "from_settings liefert nicht dieselben Pfade wie der Vorgabewert des "
        "Konstruktors — ein über die Konfiguration gebauter Klient kann eine "
        "Methode nicht aufrufen."
    )


async def test_forget_funktioniert_ueber_einen_aus_der_konfiguration_gebauten_klienten() -> None:
    """Die Sache selbst, auf dem Weg, den der Betrieb geht.

    Aufbau-Kontrolle zum Test darüber: Der Schlüsselvergleich allein bliebe grün,
    wenn der Pfad zwar existierte, aber falsch zusammengesetzt würde. Hier wird
    tatsächlich gelöscht — über `from_settings`, nicht über einen von Hand
    gebauten Klienten.
    """
    gesehen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        gesehen["methode"] = request.method
        gesehen["pfad"] = request.url.path
        return httpx.Response(200, json={"deleted": True})

    transport = httpx.MockTransport(handler)
    client = SubstrateClient.from_settings(
        Settings(substrate_base_url="https://gedaechtnis.example"),
        client=httpx.AsyncClient(base_url="https://gedaechtnis.example", transport=transport),
    )

    antwort = await client.forget("abc-123")

    assert gesehen["methode"] == "DELETE"
    assert str(gesehen["pfad"]).endswith("/abc-123")
    assert antwort == {"deleted": True}


# ------------------------------------------------------------
#  Der Bereich steht im Löschpfad — eine Quelle, nicht zwei
# ------------------------------------------------------------


def _aus_konfiguration(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    forget_path: str = "/api/substrate/forget",
    namespace: str = "foreman",
    ueberschreib_namespace: str | None = None,
) -> SubstrateClient:
    """Klient auf dem Weg, den der Betrieb geht — mit echtem Transport (B4)."""
    transport = httpx.MockTransport(handler)
    return SubstrateClient.from_settings(
        Settings(
            substrate_base_url="http://substrate.test",
            substrate_forget_path=forget_path,
            substrate_namespace=namespace,
        ),
        namespace=ueberschreib_namespace,
        client=httpx.AsyncClient(transport=transport, base_url="http://substrate.test"),
    )


@pytest.mark.parametrize(
    ("basispfad", "namespace"),
    [
        ("/api/substrate/forget", "foreman"),
        ("/api/substrate/forget/", "foreman"),  # Schrägstrich am Ende darf nicht doppeln
        ("/api/substrate/forget", "foreman-demo"),  # Bindestrich im Bereich
    ],
)
async def test_forget_haengt_bereich_und_kennung_an_den_basispfad(
    basispfad: str, namespace: str
) -> None:
    """Geprüft wird die TATSÄCHLICH angefragte Adresse, nicht das Pfad-Verzeichnis (B6).

    Ein Verzeichnis kann richtig gefüllt sein und der Aufruf trotzdem falsch
    zusammengesetzt werden. Die Gegenstelle adressiert
    /{basispfad}/{bereich}/{kennung}; `forget` schickt weder Rumpf noch
    Abfrageteil, der Pfad ist also die einzige Stelle, an der der Bereich mitgeht.
    """
    gesehen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["pfad"] = request.url.path
        gesehen["methode"] = request.method
        return httpx.Response(200, json={"entry_id": "abc-123", "status": "deleted"})

    client = _aus_konfiguration(handler, forget_path=basispfad, namespace=namespace)
    await client.forget("abc-123")

    assert gesehen["methode"] == "DELETE"
    assert gesehen["pfad"] == f"/api/substrate/forget/{namespace}/abc-123"


async def test_abweichender_bereich_wirkt_auch_im_loeschpfad() -> None:
    """EINE Quelle für den Bereich — sonst schreibt der Klient anderswo, als er löscht.

    Der Round-Trip-Smoke baut seinen Klienten mit abweichendem Bereich. Käme der
    Bereich im Löschpfad aus einer zweiten Einstellung, zeigte das Löschen auf den
    Betriebsbestand, während das Schreiben im Smoke-Bestand landet. Heute ruft der
    Smoke `forget` nicht auf — die Falle ist gestellt, nicht ausgelöst, und dieser
    Test hält sie geschlossen.
    """
    gesehen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["pfad"] = request.url.path
        return httpx.Response(200, json={"status": "deleted"})

    client = _aus_konfiguration(
        handler, namespace="foreman", ueberschreib_namespace="foreman-smoke"
    )
    await client.forget("xyz")

    assert gesehen["pfad"] == "/api/substrate/forget/foreman-smoke/xyz"
    assert client._namespace == "foreman-smoke", "Klient und Löschpfad liefen auseinander"


async def test_leere_kennung_wird_vor_dem_aufruf_abgelehnt() -> None:
    """B5: Ohne Kennung zeigte der Pfad auf die Sammlung statt auf einen Eintrag."""
    gerufen = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal gerufen
        gerufen = True
        return httpx.Response(200, json={})

    client = _aus_konfiguration(handler)
    for leer in ("", "   ", "\n"):
        with pytest.raises(ValueError):
            await client.forget(leer)
    assert not gerufen, "es wurde trotz fehlender Kennung eine Anfrage geschickt"


# ------------------------------------------------------------
#  404 ist unterscheidbar — aber kein Erfolg
# ------------------------------------------------------------


async def test_404_wirft_die_eigene_ausnahme() -> None:
    """Nicht-auffindbar muss von Weg-ist-gestoert trennbar sein.

    Umgedeutet wird nichts: Es WIRFT weiterhin. Nur die Art wird unterscheidbar,
    damit ein Aufrufer entscheiden kann — vorher ging der Statuscode in
    `SubstrateError` verloren und beide Fälle sahen gleich aus.

    Der Docstring sagte hier bis zum 02.09.2026 „Ist-schon-weg". Das trug nicht:
    Die Gegenstelle liefert denselben 404 für eine abgewiesene Löschung. Siehe
    den Fall am Ende dieser Datei.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "kein solcher Eintrag"})

    client = _aus_konfiguration(handler)
    with pytest.raises(SubstrateNotFoundError):
        await client.forget("weg")


async def test_die_eigene_ausnahme_bleibt_ein_substrate_error() -> None:
    """Aufbau-Kontrolle: Bestehende Aufrufer fangen die Oberklasse und laufen weiter."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={})

    client = _aus_konfiguration(handler)
    with pytest.raises(SubstrateError):
        await client.forget("weg")


@pytest.mark.parametrize("status", [400, 401, 403, 409, 500, 503])
async def test_andere_fehlerstatus_bleiben_gewoehnliche_substrate_error(status: int) -> None:
    """Zwilling zum 404-Fall (B3).

    Ohne ihn wäre die Aussage "404 ist besonders" auch mit "alles ist besonders"
    erklärbar. Ein 500 heisst gefunden, aber nicht gelöscht — eine Störung, die
    NICHT als erledigt durchgehen darf.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"detail": "nein"})

    client = _aus_konfiguration(handler)
    with pytest.raises(SubstrateError) as fehler:
        await client.forget("abc")
    assert not isinstance(fehler.value, SubstrateNotFoundError), (
        f"HTTP {status} wurde faelschlich als nicht-gefunden gewertet"
    )


async def test_netzfehler_bleibt_gewoehnlicher_substrate_error() -> None:
    """Ein Verbindungsfehler trägt gar keine Antwort — immer eine Wegstörung."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("keine Verbindung (Test)")

    client = _aus_konfiguration(handler)
    with pytest.raises(SubstrateError) as fehler:
        await client.forget("abc")
    assert not isinstance(fehler.value, SubstrateNotFoundError)


async def test_erfolgreiches_loeschen_liefert_den_rumpf_durch() -> None:
    """Die Gegenstelle antwortet 200 MIT Rumpf, nicht 204.

    `_delete` liest den Rumpf bedingungslos; ein 204 ohne Inhalt liefe hier in
    einen Auswertungsfehler. Die Antwortform gehört deshalb in die Abnahme und
    nicht nur in die Absprache.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "entry_id": "abc-123",
                "namespace": "foreman",
                "status": "deleted",
                "tiers": ["plastic"],
            },
        )

    client = _aus_konfiguration(handler)
    antwort = await client.forget("abc-123")
    assert antwort["status"] == "deleted"
    assert antwort["entry_id"] == "abc-123"


# ------------------------------------------------------------
#  Der 404 belegt NICHT, dass der Eintrag fort ist
# ------------------------------------------------------------
async def test_der_404_behauptet_nicht_dass_der_eintrag_fort_ist() -> None:
    """DER TRAGENDE FALL (Substrat-Befund der Gegenstelle, 02.09.2026).

    Der Löschweg der Gegenstelle liefert 404 auch für eine ABGEWIESENE Löschung —
    beide Fälle enden dort in derselben leeren Ebenenliste. Wer die Meldung als
    „ist schon weg" liest, bucht ein Löschverlangen als erfüllt, das es nicht ist,
    und verwirft dabei den einzigen Rückweg zu einem Eintrag, der weiterlebt.

    WARUM HIER DER WORTLAUT GEPRÜFT WIRD und nicht ein Verhalten: Die Ungewissheit
    ist am Statuscode nicht zu trennen, und der Antwortkörper gibt nichts her. Die
    Meldung ist damit das EINZIGE, was sie zu einem Menschen trägt — sie ist hier
    der Mechanismus, nicht seine Beschreibung. Eine erfundene Unterscheidung wäre
    schlimmer als die Ungewissheit.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Loeschung verweigert"})

    client = _aus_konfiguration(handler)
    with pytest.raises(SubstrateNotFoundError) as fehler:
        await client.forget("weg")

    meldung = str(fehler.value)
    assert "nicht auffindbar" in meldung
    assert "ABGEWIESENE" in meldung, (
        "❌ Die Meldung benennt die Mehrdeutigkeit nicht — dann liest sie sich wie "
        "ein Beleg der Löschung."
    )
    assert "KEIN Beleg" in meldung
    assert "Loeschung verweigert" in meldung, (
        "❌ Der Antwortkörper fehlt. Er trennt die beiden Fälle zwar nicht, ist aber "
        "die einzige Spur, die einem Menschen später noch etwas sagen könnte."
    )


async def test_ein_leerer_rumpf_macht_die_meldung_nicht_unleserlich() -> None:
    """AUFBAU-KONTROLLE: Ohne Rumpf steht dort etwas Lesbares statt einer Lücke."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _aus_konfiguration(handler)
    with pytest.raises(SubstrateNotFoundError) as fehler:
        await client.forget("weg")
    assert "(leer)" in str(fehler.value)


# ──────────────────────────────────────────────────────────────────────
#  Ohne Token wird es laut — einmal je Prozess
# ──────────────────────────────────────────────────────────────────────


def _substrat_einstellungen(token: str | None) -> Settings:
    return Settings(
        _env_file=None, substrate_base_url="http://substrate.test", substrate_token=token
    )


def _tokenwarnungen(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if "SUBSTRATE_TOKEN" in r.getMessage()]


def test_ohne_token_wird_beim_bau_laut_gewarnt(caplog: pytest.LogCaptureFixture) -> None:
    """DER TRAGENDE FALL: Base-URL gesetzt, Token fehlt → eine Alarmzeile.

    ANLASS (03.09.2026): Der Live-Worker lief seit dem 25.06. ohne SUBSTRATE_TOKEN,
    weil die Variable in seinem Dienst nie gesetzt war. `from_settings` baute einen
    Klienten ohne Authorization-Kopf, nichts warf, nichts meldete. Aufgefallen ist es
    erst, als die Gegenstelle bei einer Token-Rotation in die Variablen sah.
    """
    client_modul._GEMELDET.clear()
    with caplog.at_level(logging.WARNING, logger="foreman.substrate.client"):
        SubstrateClient.from_settings(_substrat_einstellungen(None))
    warnungen = _tokenwarnungen(caplog)
    assert len(warnungen) == 1, warnungen
    assert "401" in warnungen[0], "die Zeile muss sagen, WAS passieren wird"


def test_mit_token_keine_warnung(caplog: pytest.LogCaptureFixture) -> None:
    """AUFBAU-KONTROLL-ZWILLING: Mit Token bleibt es still.

    Ohne diesen Fall bliebe der Fall darüber auch dann grün, wenn die Warnung
    bedingungslos käme — und eine Warnung, die immer kommt, liest niemand.
    """
    client_modul._GEMELDET.clear()
    with caplog.at_level(logging.WARNING, logger="foreman.substrate.client"):
        SubstrateClient.from_settings(_substrat_einstellungen("tok"))
    assert _tokenwarnungen(caplog) == []


def test_die_warnung_kommt_einmal_je_prozess(caplog: pytest.LogCaptureFixture) -> None:
    """Das Backend baut je Anfrage einen Klienten (api/deps.py).

    Eine Meldung je Anfrage wäre Lärm, den ein Betreiber nach der dritten Zeile
    ausblendet — und damit auch die eine, die zählt.
    """
    client_modul._GEMELDET.clear()
    with caplog.at_level(logging.WARNING, logger="foreman.substrate.client"):
        SubstrateClient.from_settings(_substrat_einstellungen(None))
        SubstrateClient.from_settings(_substrat_einstellungen(None))
    assert len(_tokenwarnungen(caplog)) == 1
