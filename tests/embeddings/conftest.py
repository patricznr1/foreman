# ============================================================
#  FOREMAN — tests/embeddings/conftest.py
#  Zweck: Test-Infrastruktur der Embedding-Schicht (F-SEM). Ein deterministisches
#         Mock-Backend (EmbeddingBackend-Protokoll) + Fabriken für das ECHTE
#         LocalEmbeddingProvider — so laufen L2-Normalisierung, Dim-Check und
#         Priority/Fallback real durch (kein Netz, kein Modell-Download).
#         Bewusst lokal definiert (analog zur F6-conftest), eigenständig.
# ============================================================
from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest

from foreman.embeddings import LocalEmbeddingProvider, Priority
from foreman.embeddings.errors import ProviderUnavailable


class MockEmbeddingBackend:
    """Deterministisches Mock-Backend (EmbeddingBackend-Protokoll), kein Netz.

    Modi: feste Vektorliste (`vectors`), Default-Vektor der Länge `dim` je Text,
    oder Ausfall (`fail`). `calls` zählt die Batch-Aufrufe (Batch-Garantie testen).
    """

    def __init__(
        self,
        name: str = "ollama",
        *,
        dim: int = 1024,
        vectors: Sequence[Sequence[float]] | None = None,
        fail: bool = False,
    ) -> None:
        self.name = name
        self._dim = dim
        self._vectors = vectors
        self._fail = fail
        self.calls = 0

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[list[float]]:
        self.calls += 1
        if self._fail:
            raise ProviderUnavailable(
                f"❌ {self.name} nicht erreichbar (Mock)", attempted=(self.name,)
            )
        if self._vectors is not None:
            return [list(v) for v in self._vectors]
        # Default: ein deterministischer (unnormalisierter) Vektor je Text.
        return [[float((i + 1) % 7) for i in range(self._dim)] for _ in texts]


@pytest.fixture
def make_embed_backend() -> Callable[..., MockEmbeddingBackend]:
    """Fabrik für konfigurierte Mock-Embedding-Backends."""

    def _make(name: str = "ollama", **kwargs: object) -> MockEmbeddingBackend:
        return MockEmbeddingBackend(name, **kwargs)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_provider() -> Callable[..., LocalEmbeddingProvider]:
    """Fabrik fürs ECHTE LocalEmbeddingProvider über Mock-Backends (deterministisch)."""

    def _make(
        *,
        backends: Sequence[object],
        priority: Priority = "ollama_only",
        dimension: int = 1024,
        normalize: bool = True,
        timeout_s: float = 30.0,
    ) -> LocalEmbeddingProvider:
        return LocalEmbeddingProvider(
            backends=backends,  # type: ignore[arg-type]
            priority=priority,
            dimension=dimension,
            normalize=normalize,
            timeout_s=timeout_s,
        )

    return _make
