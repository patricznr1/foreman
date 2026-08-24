# ============================================================
#  FOREMAN — tests/unit/test_substrate_client.py
#  Zweck: SubstrateClient + Smoke gegen einen gemockten HTTP-Endpunkt (§9).
#  Kein echtes Substrat nötig — httpx.MockTransport simuliert die Antworten.
# ============================================================
from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from foreman.config import Settings
from foreman.substrate.client import (
    SubstrateClient,
    SubstrateError,
    SubstrateNotConfiguredError,
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
