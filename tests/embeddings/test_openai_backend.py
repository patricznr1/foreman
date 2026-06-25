# ============================================================
#  FOREMAN — tests/embeddings/test_openai_backend.py
#  Zweck: Das OpenAI-Cloud-Embedding-Backend (F-SEM, optionaler Demo-Pfad) über
#         httpx-MockTransport (kein Netz, kein Key nach außen). Geprüft wird der
#         EmbeddingBackend-Vertrag analog OllamaBackend: ein Vektor je Text in
#         INPUT-Reihenfolge (Sortierung über data[].index), die Übersetzung jeder
#         httpx-Ausnahme in einen typisierten Embedding-Fehler (Architektur-Grenze
#         §15.2), die defensive Antwort-Verarbeitung, der Provider-Dimension-Guard
#         (1024) und das Routing (resolve_chain/from_settings) der openai-Modi.
#  Konvention: deutsche Test-Namen; ✅ Pass / ❌ Fail über Assert-Messages.
# ============================================================
from __future__ import annotations

import json

import httpx
import pytest

from foreman.embeddings import (
    DimensionMismatch,
    EmbeddingSettings,
    LocalEmbeddingProvider,
    ProviderUnavailable,
)
from foreman.embeddings.backends import (
    OPENAI_BACKEND,
    OllamaBackend,
    OpenAIBackend,
    SentenceTransformersBackend,
    resolve_chain,
)
from foreman.embeddings.config import OLLAMA_BACKEND, ST_BACKEND
from foreman.embeddings.errors import EmbeddingTimeout


def _openai(
    handler: object,
    *,
    model: str = "text-embedding-3-small",
    dimensions: int = 1024,
    api_key: str = "sk-test-123",
    base_url: str = "https://api.openai.test/v1",
) -> OpenAIBackend:
    """Baut ein OpenAIBackend mit injiziertem MockTransport-Client (kein Netz)."""
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    return OpenAIBackend(
        base_url=base_url,
        model=model,
        api_key=api_key,
        dimensions=dimensions,
        client=client,
    )


# ----------------------------------------------------------------
#  Happy-Path: data[].embedding, vertauschte index-Reihenfolge
# ----------------------------------------------------------------
async def test_openai_embed_batch_stellt_input_reihenfolge_her() -> None:
    # OpenAI darf data[] in beliebiger Reihenfolge liefern → Sortierung über `index`.
    vec0 = [0.5, *([0.0] * 1023)]
    vec1 = [0.25, *([0.0] * 1023)]
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        # index absichtlich vertauscht (1 vor 0) — Backend muss zurücksortieren.
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "text-embedding-3-small",
                "data": [
                    {"object": "embedding", "index": 1, "embedding": vec1},
                    {"object": "embedding", "index": 0, "embedding": vec0},
                ],
            },
        )

    backend = _openai(handler)
    vectors = await backend.embed_batch(["a", "b"], timeout_s=5.0)

    assert len(vectors) == 2, "❌ Fail: erwartet zwei Vektoren (ein Batch-Call)"
    assert len(vectors[0]) == 1024 and len(vectors[1]) == 1024, "❌ Fail: 1024-dim erwartet"
    # Reihenfolge folgt dem INPUT (["a","b"] → index 0,1), nicht der Antwort-Reihenfolge.
    assert vectors[0][0] == pytest.approx(0.5), "❌ Fail: Vektor für 'a' (index 0) zuerst"
    assert vectors[1][0] == pytest.approx(0.25), "❌ Fail: Vektor für 'b' (index 1) danach"
    # Request-Vertrag: Endpoint, Bearer-Auth, Body mit dimensions + encoding_format.
    assert str(seen["url"]).endswith("/v1/embeddings"), "❌ Fail: {base}/embeddings erwartet"
    assert seen["auth"] == "Bearer sk-test-123", "❌ Fail: Authorization-Bearer-Header erwartet"
    assert seen["body"] == {
        "model": "text-embedding-3-small",
        "input": ["a", "b"],
        "dimensions": 1024,
        "encoding_format": "float",
    }, "❌ Fail: Body-Vertrag (model/input/dimensions/encoding_format)"
    # ✅ Pass: Reihenfolge wiederhergestellt + Request-Vertrag korrekt.


# ----------------------------------------------------------------
#  Timeout → EmbeddingTimeout
# ----------------------------------------------------------------
async def test_openai_timeout_wird_embedding_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("zu langsam")

    backend = _openai(handler)
    with pytest.raises(EmbeddingTimeout):
        await backend.embed_batch(["x"], timeout_s=0.01)
    # ✅ Pass: httpx.TimeoutException → typisierter EmbeddingTimeout.


# ----------------------------------------------------------------
#  HTTP-Fehler (500/401) → ProviderUnavailable(attempted=("openai",))
# ----------------------------------------------------------------
@pytest.mark.parametrize("status", [500, 401])
async def test_openai_http_fehler_wird_provider_unavailable(status: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": "boom"}})

    backend = _openai(handler)
    with pytest.raises(ProviderUnavailable) as exc:
        await backend.embed_batch(["x"], timeout_s=5.0)
    assert exc.value.attempted == (OPENAI_BACKEND,), "❌ Fail: attempted=('openai',) erwartet"
    # ✅ Pass: HTTP-Statusfehler → ProviderUnavailable mit attempted-Liste.


# ----------------------------------------------------------------
#  Edge: unverwertbare Antwort → ProviderUnavailable
# ----------------------------------------------------------------
async def test_openai_kein_data_feld_wird_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"object": "list", "kein_data": True})

    backend = _openai(handler)
    with pytest.raises(ProviderUnavailable):
        await backend.embed_batch(["x"], timeout_s=5.0)
    # ✅ Pass: fehlendes data-Array → unverwertbar.


async def test_openai_falsche_treffer_anzahl_wird_provider_unavailable() -> None:
    # Ein Vektor für zwei Texte → Cardinality verletzt (kein stilles Auffüllen).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})

    backend = _openai(handler)
    with pytest.raises(ProviderUnavailable):
        await backend.embed_batch(["a", "b"], timeout_s=5.0)
    # ✅ Pass: Treffer-Anzahl ≠ Text-Anzahl → unverwertbar.


async def test_openai_fehlendes_embedding_feld_wird_provider_unavailable() -> None:
    # data[]-Eintrag ohne 'embedding' → unverwertbar (keine rohe KeyError nach oben).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "kein_embedding": []}]})

    backend = _openai(handler)
    with pytest.raises(ProviderUnavailable):
        await backend.embed_batch(["x"], timeout_s=5.0)
    # ✅ Pass: defektes data-Item → ProviderUnavailable statt Library-Ausnahme.


# ----------------------------------------------------------------
#  Provider-Dimension-Guard: 512-dim Antwort bei dimension=1024 → DimensionMismatch
# ----------------------------------------------------------------
async def test_provider_openai_512_dim_wirft_dimension_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # korrekte Treffer-Anzahl (1), aber falsche Länge (512 statt 1024).
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.01] * 512}]})

    backend = _openai(handler, dimensions=512)
    provider = LocalEmbeddingProvider(
        backends=[backend],
        priority="openai_only",
        dimension=1024,
        normalize=True,
        timeout_s=5.0,
    )
    with pytest.raises(DimensionMismatch):
        await provider.embed(["x"])
    # ✅ Pass: 512 ≠ 1024 → DimensionMismatch (würde sonst Insert/Index brechen).


# ----------------------------------------------------------------
#  Routing: resolve_chain + from_settings (nur OpenAIBackend, kein Ollama/ST)
# ----------------------------------------------------------------
def test_resolve_chain_openai_modi() -> None:
    assert resolve_chain("openai_only") == (OPENAI_BACKEND,)
    # openai_first hält den Fallback-Slot offen, fällt aber bewusst NICHT auf die
    # lokalen Backends zurück (Cloud-Demo-Setup) → derzeit effektiv wie openai_only.
    assert resolve_chain("openai_first") == (OPENAI_BACKEND,)
    # ✅ Pass: beide openai-Modi sind definiert und enthalten nur das Cloud-Backend.


def test_from_settings_baut_nur_openai_backend() -> None:
    settings = EmbeddingSettings(
        _env_file=None,  # type: ignore[call-arg]
        priority="openai_only",
        openai_api_key="sk-test-456",
    )
    provider = LocalEmbeddingProvider.from_settings(settings)

    # Genau ein Backend, und zwar das OpenAI-Backend — kein Ollama/ST instanziiert.
    assert set(provider._backends) == {OPENAI_BACKEND}, "❌ Fail: nur 'openai' erwartet"
    assert OLLAMA_BACKEND not in provider._backends
    assert ST_BACKEND not in provider._backends
    built = provider._backends[OPENAI_BACKEND]
    assert isinstance(built, OpenAIBackend), "❌ Fail: OpenAIBackend erwartet"
    assert not isinstance(built, (OllamaBackend, SentenceTransformersBackend))
    assert built.model == "text-embedding-3-small", "❌ Fail: Default-Modell durchgereicht"
    # ✅ Pass: from_settings baut nur das OpenAIBackend für den openai_only-Modus.


def test_openai_backend_name_konstante() -> None:
    assert OPENAI_BACKEND == "openai"
    assert OpenAIBackend.name == OPENAI_BACKEND
    # ✅ Pass: niedrig-kardinales Metrik-Label 'openai'.


async def test_openai_nicht_json_body_wird_provider_unavailable() -> None:
    # 200, aber kein JSON-Body (z. B. Proxy-HTML/abgeschnittene Antwort) → response.json()
    # wirft eine ValueError-Subklasse; sie darf die Architektur-Grenze §15.2 NICHT als
    # rohe Library-Ausnahme verlassen (Such-/Backfill-Pfad propagieren ehrlich, §15.3).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>kaputt</html>")

    backend = _openai(handler)
    with pytest.raises(ProviderUnavailable):
        await backend.embed_batch(["x"], timeout_s=5.0)
    # ✅ Pass: nicht-JSON-Body → ProviderUnavailable statt roher ValueError.


async def test_from_settings_ohne_key_baut_kein_backend() -> None:
    # Kein Key gesetzt (Cloud-Pfad nicht scharf): from_settings crasht nicht, baut
    # aber KEIN OpenAI-Backend → embed() degradiert lokal zu ProviderUnavailable,
    # OHNE dass (NER-maskierter) Notiz-Text das System Richtung US-Cloud verlässt
    # (§8/§18 — keine Text-Exfiltration ohne echten Key).
    settings = EmbeddingSettings(
        _env_file=None,  # type: ignore[call-arg]
        priority="openai_only",
    )
    provider = LocalEmbeddingProvider.from_settings(settings)
    assert OPENAI_BACKEND not in provider._backends, "❌ Fail: ohne Key kein OpenAI-Backend"
    with pytest.raises(ProviderUnavailable):
        await provider.embed(["x"])  # lokale Degradation, KEIN externer Request
    # ✅ Pass: ohne Key kein Backend → lokale Degradation statt Cloud-Request.


@pytest.mark.parametrize(
    "data_items",
    [
        [{"embedding": [0.1] * 4}],  # index fehlt
        [{"index": "0", "embedding": [0.1] * 4}],  # index nicht-ganzzahlig
        [{"index": 5, "embedding": [0.1] * 4}],  # index nicht in 0..n-1 (n=1)
        [  # doppelter index für zwei Texte (n=2) → keine dichte Permutation
            {"index": 0, "embedding": [0.1] * 4},
            {"index": 0, "embedding": [0.2] * 4},
        ],
    ],
)
async def test_openai_defekter_index_wird_provider_unavailable(
    data_items: list[dict[str, object]],
) -> None:
    # data[].index MUSS eine dichte 0..n-1-Permutation sein — fehlende/doppelte/
    # nicht-ganzzahlige Indizes dürfen NICHT still zu falscher Zuordnung führen.
    texts = ["a", "b"] if len(data_items) > 1 else ["a"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": data_items})

    backend = _openai(handler)
    with pytest.raises(ProviderUnavailable):
        await backend.embed_batch(texts, timeout_s=5.0)
    # ✅ Pass: inkonsistente data[].index-Werte → ProviderUnavailable.


async def test_openai_reicht_timeout_pro_request_durch() -> None:
    # Der Methoden-Timeout muss PRO Request gesetzt werden — auch bei injiziertem
    # Client, dessen Default-Timeout abweicht (12.5 ≠ httpx-Default 5.0s).
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["timeout"] = request.extensions.get("timeout")
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1] * 4}]})

    backend = _openai(handler)
    await backend.embed_batch(["x"], timeout_s=12.5)
    timeout = seen["timeout"]
    assert isinstance(timeout, dict) and timeout.get("read") == 12.5, (
        "❌ Fail: timeout_s wird nicht pro Request durchgereicht"
    )
    # ✅ Pass: timeout_s wird an client.post weitergereicht.
