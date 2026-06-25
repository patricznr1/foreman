# ============================================================
#  FOREMAN — embeddings/backends.py
#  Zweck: Backend-Auflösung/Routing der Embedding-Schicht (F-SEM) — lokales
#         Ollama-Backend (bge-m3 über httpx) + sentence-transformers-Alternative,
#         plus die Prioritäts-/Fallback-Logik. DIES ist die EINZIGE Datei, die die
#         konkreten Embedding-Libraries berührt (sentence-transformers LAZY). Kein
#         Library-Typ verlässt dieses Modul — jede Fremd-Ausnahme wird in einen
#         typisierten Embedding-Fehler übersetzt (harte Architektur-Grenze,
#         analog §13.2 Gateway-Backends).
#  Architektur-Einordnung: Schicht 2, hinter der EmbeddingProvider-Abstraktion.
#         Beide Backends sind lokal; Async durchgängig; reine Routing-Funktionen
#         seedbar (Tests ohne Netz/Modell).
#  Konvention (§6): deutsche Kommentare, keine PII/keine Notiz-Texte/keine Vektoren
#         in Logs/Fehlern.
# ============================================================
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

import httpx

from foreman.embeddings.config import OLLAMA_BACKEND, OPENAI_BACKEND, ST_BACKEND, Priority
from foreman.embeddings.errors import EmbeddingError, EmbeddingTimeout, ProviderUnavailable

# Rohe (un-normalisierte) Vektoren, wie ein Backend sie liefert — vor Dim-Check/
# L2-Normalisierung im Provider.
RawVector = list[float]


@runtime_checkable
class EmbeddingBackend(Protocol):
    """Ein konkretes Embedding-Backend (Ollama/sentence-transformers).

    Vertrag: ein Batch von Texten → ein Roh-Vektor je Text (gleiche Reihenfolge).
    Nicht erreichbar/Timeout → typisierter Embedding-Fehler (nie Library-Ausnahme).
    """

    name: str

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[RawVector]: ...


# Priority-Modus → Reihenfolge der Backend-Namen (GROUND_TRUTH §15).
# Die openai-Modi tragen bewusst KEINEN lokalen Fallback (Cloud-Demo-Image ohne
# Ollama/sentence-transformers) — beide enthalten nur das Cloud-Backend (§15.2).
_CHAINS: dict[str, tuple[str, ...]] = {
    "ollama_first": (OLLAMA_BACKEND, ST_BACKEND),
    "st_first": (ST_BACKEND, OLLAMA_BACKEND),
    "ollama_only": (OLLAMA_BACKEND,),
    "st_only": (ST_BACKEND,),
    "openai_only": (OPENAI_BACKEND,),
    "openai_first": (OPENAI_BACKEND,),
}


def resolve_chain(priority: Priority) -> tuple[str, ...]:
    """Liefert die Backend-Reihenfolge für einen Priority-Modus (rein, seedbar)."""
    return _CHAINS[priority]


async def run_with_fallback(
    chain: Sequence[EmbeddingBackend],
    texts: Sequence[str],
    *,
    timeout_s: float,
) -> tuple[list[RawVector], EmbeddingBackend]:
    """Versucht die Backends in Reihenfolge; fällt bei Nicht-Erreichbarkeit/Timeout
    auf das nächste zurück.

    Rückgabe: (Roh-Vektoren, genutztes Backend). Ist die Kette erschöpft (oder
    leer/`*_only` mit verbotenem Fallback), wird ein sauberer `ProviderUnavailable`
    mit der Liste der versuchten Backends geworfen.
    """
    attempted: list[str] = []
    last_exc: EmbeddingError | None = None
    for backend in chain:
        attempted.append(backend.name)
        try:
            vectors = await backend.embed_batch(texts, timeout_s=timeout_s)
        except (ProviderUnavailable, EmbeddingTimeout) as exc:
            last_exc = exc
            continue
        return vectors, backend
    raise ProviderUnavailable(
        f"❌ Kein erlaubtes Embedding-Backend erreichbar (versucht: {attempted})",
        attempted=attempted,
    ) from last_exc


def _coerce_vectors(raw: Any, *, expected_count: int) -> list[RawVector]:
    """Mappt eine rohe Backend-Antwort defensiv auf eine Liste von Float-Vektoren.

    `raw` ist eine Liste von Zahlen-Listen (Embeddings). Alles andere ist eine
    unverwertbare Antwort → ProviderUnavailable (keine Library-Ausnahme nach oben).
    """
    if not isinstance(raw, list) or len(raw) != expected_count:
        raise ProviderUnavailable(
            f"❌ Embedding-Backend lieferte eine unverwertbare Antwort "
            f"(erwartet {expected_count} Vektoren)."
        )
    vectors: list[RawVector] = []
    for row in raw:
        if not isinstance(row, list):
            raise ProviderUnavailable("❌ Embedding-Backend lieferte einen unverwertbaren Vektor.")
        try:
            vectors.append([float(value) for value in row])
        except (TypeError, ValueError) as exc:
            # Architektur-Grenze: nicht-numerische Werte dürfen nicht als rohe
            # ValueError/TypeError aus der Embedding-Schicht lecken.
            raise ProviderUnavailable(
                "❌ Embedding-Backend lieferte nicht-numerische Vektor-Werte."
            ) from exc
    return vectors


class OllamaBackend:
    """Embedding-Backend über Ollama (`POST /api/embed`, Batch via `input`).

    Übersetzt jede httpx-Ausnahme in einen typisierten Embedding-Fehler — nichts
    Library-Spezifisches verlässt das Modul. Ein `httpx.AsyncClient` kann injiziert
    werden (Tests gegen MockTransport, ohne echtes Ollama)."""

    name = OLLAMA_BACKEND

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url
        self._client = client

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[RawVector]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(base_url=self._base_url, timeout=timeout_s)
        try:
            response = await client.post(
                "/api/embed",
                json={"model": self.model, "input": list(texts)},
                timeout=timeout_s,
            )
            response.raise_for_status()
            data: Any = response.json()
        except httpx.TimeoutException as exc:
            raise EmbeddingTimeout(
                f"❌ Zeitüberschreitung beim Embedding-Backend '{self.name}' (>{timeout_s}s)"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            # ValueError deckt JSONDecodeError (200 mit nicht-JSON-Body) ab — sonst
            # verließe eine rohe Library-Ausnahme die Architektur-Grenze (§15.2).
            raise ProviderUnavailable(
                f"❌ Embedding-Backend '{self.name}' nicht erreichbar", attempted=(self.name,)
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        embeddings = data.get("embeddings") if isinstance(data, dict) else None
        return _coerce_vectors(embeddings, expected_count=len(texts))


def _extract_openai_embeddings(data: Any, *, expected_count: int) -> Any:
    """Zieht die Embeddings aus einer OpenAI-`/embeddings`-Antwort und stellt die
    INPUT-Reihenfolge über `data[].index` wieder her.

    OpenAI darf die Einträge in beliebiger Reihenfolge liefern; die Vertrags-Garantie
    „ein Vektor je Text in Eingabe-Reihenfolge" stellt die Sortierung über `index`
    sicher. Defensiv: jede unerwartete Form (kein `data`-Array, fehlendes `index`/
    `embedding`) wird zu `ProviderUnavailable` — keine Library-Ausnahme nach oben.
    Die finale Form-/Längen-/Typprüfung übernimmt anschließend `_coerce_vectors`.
    """
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ProviderUnavailable(
            "❌ Embedding-Backend 'openai' lieferte eine unverwertbare Antwort "
            "(kein 'data'-Array).",
            attempted=(OPENAI_BACKEND,),
        )
    try:
        ordered = sorted(items, key=lambda item: item["index"])
        indices = [item["index"] for item in ordered]
        embeddings = [item["embedding"] for item in ordered]
    except (KeyError, TypeError) as exc:
        raise ProviderUnavailable(
            "❌ Embedding-Backend 'openai' lieferte eine unverwertbare Antwort.",
            attempted=(OPENAI_BACKEND,),
        ) from exc
    # `data[].index` muss eine dichte 0..n-1-Permutation sein — doppelte/lückenhafte/
    # nicht-ganzzahlige Indizes (gleiche Anzahl, falsche Zuordnung) würden sonst still
    # durchrutschen und ein Embedding dem falschen Eingabetext zuordnen.
    if indices != list(range(expected_count)):
        raise ProviderUnavailable(
            "❌ Embedding-Backend 'openai' lieferte inkonsistente data[].index-Werte.",
            attempted=(OPENAI_BACKEND,),
        )
    return embeddings


class OpenAIBackend:
    """Embedding-Backend über die OpenAI-API (`POST {base_url}/embeddings`).

    Optionaler Cloud-Pfad (Demo, US-Drittland — §15.2/§18): `text-embedding-3-small`
    mit `dimensions=1024` passt OHNE Migration in `worker_notes.embedding`
    (`vector(1024)`). Reines httpx wie `OllamaBackend` — KEIN openai-SDK; nichts
    Library-Spezifisches verlässt das Modul, jede httpx-Ausnahme wird in einen
    typisierten Embedding-Fehler übersetzt. Der API-Key wird NIE geloggt oder in
    Fehlern wiedergegeben (§8/§15.7). Ein `httpx.AsyncClient` kann injiziert werden
    (Tests gegen MockTransport, ohne Netz)."""

    name = OPENAI_BACKEND

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        dimensions: int,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        # Vollständiger Endpoint: base_url trägt einen Pfad (`/v1`) → ein relativer
        # httpx-base_url-Join würde das `/v1` verschlucken, darum explizit bauen.
        self._endpoint = f"{base_url.rstrip('/')}/embeddings"
        self._api_key = api_key
        self._dimensions = dimensions
        self._client = client

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[RawVector]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=timeout_s)
        try:
            response = await client.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self.model,
                    "input": list(texts),
                    "dimensions": self._dimensions,
                    "encoding_format": "float",
                },
                timeout=timeout_s,
            )
            response.raise_for_status()
            data: Any = response.json()
        except httpx.TimeoutException as exc:
            raise EmbeddingTimeout(
                f"❌ Zeitüberschreitung beim Embedding-Backend '{self.name}' (>{timeout_s}s)"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            # ValueError deckt JSONDecodeError (200 mit nicht-JSON-Body) ab — sonst
            # verließe eine rohe Library-Ausnahme die Architektur-Grenze (§15.2).
            raise ProviderUnavailable(
                f"❌ Embedding-Backend '{self.name}' nicht erreichbar", attempted=(self.name,)
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        return _coerce_vectors(
            _extract_openai_embeddings(data, expected_count=len(texts)),
            expected_count=len(texts),
        )


class SentenceTransformersBackend:
    """Embedding-Backend über sentence-transformers (Alternative zu Ollama).

    Die schwere Library + das Modell werden LAZY beim ersten echten Aufruf geladen
    (kein zweites Modell im API-Prozess, solange ungenutzt). `encode_fn` ist ein
    Injektionspunkt für deterministische Tests ohne Modell-Download. Jede
    Fremd-Ausnahme (inkl. fehlender Library) wird zu ProviderUnavailable."""

    name = ST_BACKEND

    def __init__(
        self,
        *,
        model_name: str,
        device: str = "cpu",
        encode_fn: Any | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._encode_fn = encode_fn
        self._model: Any | None = None

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[RawVector]:
        try:
            if self._encode_fn is not None:
                raw = await self._encode_fn(list(texts))
            else:
                raw = await asyncio.to_thread(self._encode_sync, list(texts))
        except EmbeddingError:
            raise
        except Exception as exc:  # Library-/Modell-/Import-Fehler kapseln (Architektur-Grenze)
            raise ProviderUnavailable(
                f"❌ Embedding-Backend '{self.name}' nicht verfügbar", attempted=(self.name,)
            ) from exc
        return _coerce_vectors(raw, expected_count=len(texts))

    def _encode_sync(
        self, texts: list[str]
    ) -> list[RawVector]:  # pragma: no cover - braucht Modell
        """Blockierender Encode-Pfad (in einen Thread ausgelagert). Lädt Library/Modell lazy."""
        from sentence_transformers import SentenceTransformer  # lazy: nur bei echter Nutzung

        if self._model is None:
            self._model = SentenceTransformer(self._model_name, device=self._device)
        result = self._model.encode(texts, normalize_embeddings=False)
        return [[float(value) for value in row] for row in result]
