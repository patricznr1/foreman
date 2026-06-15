# ============================================================
#  FOREMAN — tests/embeddings/test_backends.py
#  Zweck: Die konkreten Embedding-Backends (F-SEM, Baustein 1) — Ollama über
#         httpx-MockTransport (kein echtes Ollama) und sentence-transformers über
#         den injizierten encode_fn (kein Modell-Download). Plus die reinen
#         Routing-Funktionen (resolve_chain / run_with_fallback). Geprüft wird die
#         Architektur-Grenze: jede Library-/HTTP-Ausnahme wird zu einem typisierten
#         Embedding-Fehler — nichts Library-Spezifisches verlässt das Modul.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

import httpx
import pytest

from foreman.embeddings.backends import (
    OllamaBackend,
    RawVector,
    SentenceTransformersBackend,
    resolve_chain,
    run_with_fallback,
)
from foreman.embeddings.config import OLLAMA_BACKEND, ST_BACKEND
from foreman.embeddings.errors import EmbeddingTimeout, ProviderUnavailable


def _ollama(handler: object, *, model: str = "bge-m3") -> OllamaBackend:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport, base_url="http://ollama.test")
    return OllamaBackend(base_url="http://ollama.test", model=model, client=client)


# ----------------------------------------------------------------
#  OllamaBackend (httpx-MockTransport)
# ----------------------------------------------------------------
async def test_ollama_embed_batch_liefert_vektor_pro_text() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]})

    backend = _ollama(handler)
    vectors = await backend.embed_batch(["a", "b"], timeout_s=5.0)
    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    # Ein Batch-Call mit allen Texten unter `input` (nicht pro Text).
    assert seen["url"] == "http://ollama.test/api/embed"
    assert seen["body"] == {"model": "bge-m3", "input": ["a", "b"]}


async def test_ollama_http_fehler_wird_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    backend = _ollama(handler)
    with pytest.raises(ProviderUnavailable):
        await backend.embed_batch(["x"], timeout_s=5.0)


async def test_ollama_timeout_wird_embedding_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("zu langsam")

    backend = _ollama(handler)
    with pytest.raises(EmbeddingTimeout):
        await backend.embed_batch(["x"], timeout_s=0.01)


async def test_ollama_unverwertbare_antwort_wird_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"kein_embeddings_feld": True})

    backend = _ollama(handler)
    with pytest.raises(ProviderUnavailable):
        await backend.embed_batch(["x"], timeout_s=5.0)


async def test_ollama_falsche_treffer_anzahl_wird_provider_unavailable() -> None:
    # Backend liefert weniger Vektoren als Texte → unverwertbar (kein stilles Auffüllen).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})

    backend = _ollama(handler)
    with pytest.raises(ProviderUnavailable):
        await backend.embed_batch(["a", "b"], timeout_s=5.0)


# ----------------------------------------------------------------
#  SentenceTransformersBackend (injizierter encode_fn)
# ----------------------------------------------------------------
async def test_st_backend_nutzt_injizierten_encode_fn() -> None:
    async def fake_encode(texts: list[str]) -> list[RawVector]:
        return [[float(len(t))] * 3 for t in texts]

    backend = SentenceTransformersBackend(model_name="x", encode_fn=fake_encode)
    vectors = await backend.embed_batch(["ab", "cde"], timeout_s=5.0)
    assert vectors == [[2.0, 2.0, 2.0], [3.0, 3.0, 3.0]]


async def test_st_backend_fehler_wird_provider_unavailable() -> None:
    async def boom(texts: list[str]) -> list[RawVector]:
        raise RuntimeError("Modell kaputt")

    backend = SentenceTransformersBackend(model_name="x", encode_fn=boom)
    with pytest.raises(ProviderUnavailable):
        await backend.embed_batch(["x"], timeout_s=5.0)


# ----------------------------------------------------------------
#  Reine Routing-Funktionen
# ----------------------------------------------------------------
def test_resolve_chain_alle_modi() -> None:
    assert resolve_chain("ollama_first") == (OLLAMA_BACKEND, ST_BACKEND)
    assert resolve_chain("st_first") == (ST_BACKEND, OLLAMA_BACKEND)
    assert resolve_chain("ollama_only") == (OLLAMA_BACKEND,)
    assert resolve_chain("st_only") == (ST_BACKEND,)


class _StubBackend:
    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self._fail = fail
        self.calls = 0

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[RawVector]:
        self.calls += 1
        if self._fail:
            raise ProviderUnavailable(f"{self.name} aus", attempted=(self.name,))
        return [[1.0] for _ in texts]


async def test_run_with_fallback_nimmt_erstes_erreichbares() -> None:
    first = _StubBackend("ollama", fail=True)
    second = _StubBackend("sentence_transformers")
    vectors, used = await run_with_fallback([first, second], ["x"], timeout_s=5.0)
    assert vectors == [[1.0]]
    assert used.name == "sentence_transformers"
    assert first.calls == 1


async def test_run_with_fallback_erschoepft_wirft_provider_unavailable() -> None:
    only = _StubBackend("ollama", fail=True)
    with pytest.raises(ProviderUnavailable) as exc:
        await run_with_fallback([only], ["x"], timeout_s=5.0)
    assert "ollama" in exc.value.attempted
