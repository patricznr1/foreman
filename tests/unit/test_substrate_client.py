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
