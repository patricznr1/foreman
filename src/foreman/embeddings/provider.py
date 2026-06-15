# ============================================================
#  FOREMAN — embeddings/provider.py
#  Zweck: Die EmbeddingProvider-Abstraktion (F-SEM) — die EINZIGE Schnittstelle,
#         die ein Aufrufer (Ingestion, Reasoner, Such-Route) berührt: das
#         EmbeddingProvider-Protokoll (Batch-`embed`) + die konkrete
#         LocalEmbeddingProvider-Orchestrierung. Kein Aufrufer sieht ein Backend-/
#         Library-Typ (harte Architektur-Grenze, analog §13 Gateway).
#  Architektur-Einordnung: Schicht 2 — die Abstraktion, auf der Schreibpfad,
#         Suche und der Ereignisketten-Reasoner aufsetzen. Async durchgängig.
#  Verantwortung des Orchestrators: Batch-Routing/Fallback an die Backends,
#         Dimension-Erzwingung (vector(1024)), L2-Normalisierung (Cosine), Metriken
#         + strukturierter Log (keine PII/keine Notiz-Texte/keine Vektoren).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

import math
from collections.abc import Awaitable, Callable, Sequence
from time import perf_counter
from typing import Protocol, runtime_checkable

from foreman.embeddings.backends import (
    EmbeddingBackend,
    OllamaBackend,
    RawVector,
    SentenceTransformersBackend,
    resolve_chain,
    run_with_fallback,
)
from foreman.embeddings.config import OLLAMA_BACKEND, ST_BACKEND, EmbeddingSettings, Priority
from foreman.embeddings.errors import DimensionMismatch, EmbeddingError
from foreman.logging_setup import REASON, get_logger
from foreman.observability.metrics import observe_embedding

logger = get_logger("foreman.embeddings.provider")

# Ein (i. d. R. L2-normalisierter) Embedding-Vektor. Dimension = Settings.dimension;
# passt 1:1 auf worker_notes.embedding vector(1024) (GROUND_TRUTH §5).
Vector = list[float]

# Signatur des sentence-transformers-Encode-Injektionspunkts (Tests ohne Modell).
EncodeFn = Callable[[list[str]], Awaitable[list[RawVector]]]


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Das Protokoll, das Aufrufer konsumieren — die gesamte Embedding-Oberfläche.

    Ein Aufrufer übergibt einen Batch von Texten und erhält einen Vektor je Text
    (gleiche Reihenfolge), dimensions-geprüft und (per Default) L2-normalisiert.
    Keine Backend-/Library-Typen in der Signatur.
    """

    async def embed(self, texts: Sequence[str]) -> list[Vector]: ...


def _l2_normalize(vector: RawVector) -> Vector:
    """Skaliert einen Vektor auf Länge 1 (Cosine-Distanz im HNSW-Index).

    Ein reiner Nullvektor bleibt unverändert (keine Division durch Null) — er trägt
    keine Richtung und wird vom Index-Vergleich ohnehin neutral behandelt.
    """
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return list(vector)
    return [component / norm for component in vector]


class LocalEmbeddingProvider:
    """Konkrete EmbeddingProvider-Implementierung über lokale Backends.

    Orchestriert pro `embed()`: Backend-Routing/Fallback (Ollama/ST) → Dimension-
    Erzwingung → L2-Normalisierung → Metriken + strukturierter Log. Die konkreten
    Libraries bleiben vollständig in `backends.py` gekapselt — diese Klasse (und
    alles, was ein Aufrufer sieht) kennt nur FOREMAN-Typen.
    """

    def __init__(
        self,
        *,
        backends: Sequence[EmbeddingBackend],
        priority: Priority,
        dimension: int,
        normalize: bool,
        timeout_s: float,
    ) -> None:
        self._backends: dict[str, EmbeddingBackend] = {
            backend.name: backend for backend in backends
        }
        self._priority = priority
        self._dimension = dimension
        self._normalize = normalize
        self._timeout_s = timeout_s

    @classmethod
    def from_settings(
        cls,
        settings: EmbeddingSettings,
        *,
        st_encode_fn: EncodeFn | None = None,
    ) -> LocalEmbeddingProvider:
        """Baut den Provider aus der Embedding-Config. Nur die für den Priority-Modus
        nötigen Backends werden instanziiert.

        Der `st_encode_fn`-Injektionspunkt erlaubt deterministische Tests ohne
        Modell-Download. Das Ollama-Backend wird für isolierte Tests direkt mit
        einem injizierten httpx-MockTransport konstruiert (in `backends.py`), damit
        kein httpx-Typ in diese library-agnostische Schicht durchschlägt (Symmetrie
        zum Gateway-Vorbild §13: keine Library-Typen in der Provider-Fläche).
        """
        needed = set(resolve_chain(settings.priority))
        backends: list[EmbeddingBackend] = []
        if OLLAMA_BACKEND in needed:
            backends.append(
                OllamaBackend(
                    base_url=settings.local_base_url,
                    model=settings.model,
                )
            )
        if ST_BACKEND in needed:
            backends.append(
                SentenceTransformersBackend(
                    model_name=settings.st_model,
                    device=settings.st_device,
                    encode_fn=st_encode_fn,
                )
            )
        return cls(
            backends=backends,
            priority=settings.priority,
            dimension=settings.dimension,
            normalize=settings.normalize,
            timeout_s=settings.request_timeout_s,
        )

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        items = list(texts)
        if not items:
            return []

        chain_names = resolve_chain(self._priority)
        chain = [self._backends[name] for name in chain_names if name in self._backends]
        # Stabiles Backend-Label für die Fehler-Metrik (auch bei leerer/Fallback-Kette).
        primary_label = chain[0].name if chain else chain_names[0]

        t0 = perf_counter()
        try:
            raw_vectors, used = await run_with_fallback(chain, items, timeout_s=self._timeout_s)
        except EmbeddingError:
            observe_embedding(
                backend=primary_label,
                latency_seconds=perf_counter() - t0,
                success=False,
                n_texts=0,
            )
            raise

        # Dimension hart erzwingen: ein vector(1024)-Mismatch würde Insert/Index brechen.
        for vector in raw_vectors:
            if len(vector) != self._dimension:
                observe_embedding(
                    backend=used.name,
                    latency_seconds=perf_counter() - t0,
                    success=False,
                    n_texts=0,
                )
                raise DimensionMismatch(expected=self._dimension, actual=len(vector))

        result = (
            [_l2_normalize(vector) for vector in raw_vectors]
            if self._normalize
            else [list(vector) for vector in raw_vectors]
        )
        latency_s = perf_counter() - t0
        observe_embedding(
            backend=used.name, latency_seconds=latency_s, success=True, n_texts=len(items)
        )
        # Strukturierter Log (§11.1): nur Mengen/Backend/Latenz — kein Text, kein Vektor.
        logger.info(
            "%s embed backend=%s n=%s latency_ms=%.1f",
            REASON,
            used.name,
            len(items),
            latency_s * 1000.0,
        )
        return result


async def embed_best_effort(
    provider: EmbeddingProvider | None, texts: Sequence[str]
) -> list[Vector] | None:
    """Best-effort-Embedding für den Schreibpfad (Insert): Provider None / leerer
    Input / JEDER Fehler → None.

    Der Aufrufer schreibt bei None die `embedding`-Spalte als NULL; der Backfill
    (`python -m foreman.embeddings.backfill`) holt es später nach. Das Embedding
    blockiert den Notiz-Schreibpfad NIE — analog zum Substrat-Dual-Write (§12.4)
    und dem NEXUS-Recall (§14.1). Die SUCHE und der BACKFILL sind dagegen ehrlich
    (sie reichen Fehler durch).
    """
    items = list(texts)
    if provider is None or not items:
        return None
    try:
        return await provider.embed(items)
    except Exception as exc:  # best-effort: jeder Fehler → kein Embedding, nie Abbruch
        logger.warning(
            "%s Notiz-Embedding fehlgeschlagen (best-effort, embedding=NULL): %s", REASON, exc
        )
        return None
