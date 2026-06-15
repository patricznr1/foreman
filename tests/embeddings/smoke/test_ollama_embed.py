# ============================================================
#  FOREMAN — tests/embeddings/smoke/test_ollama_embed.py
#  Zweck: Echter Smoke-Round-Trip gegen lokales Ollama bge-m3 (F-SEM). Beweist,
#         dass die EmbeddingProvider-Abstraktion real durchläuft (Text → Ollama →
#         L2-normierter 1024-Vektor) — ohne CI/Default-Gate an Ollama zu koppeln:
#         ist Ollama nicht erreichbar oder bge-m3 nicht gezogen, wird SAUBER
#         übersprungen (kein Fehler).
#  Architektur-Einordnung: Quality Gate §10.6 / §15. @pytest.mark.smoke; nicht im
#         CI-Pflichtlauf (`uv run pytest -m smoke` zum gezielten Ausführen).
# ============================================================
from __future__ import annotations

import math

import httpx
import pytest

from foreman.embeddings.config import EmbeddingSettings
from foreman.embeddings.provider import LocalEmbeddingProvider

pytestmark = pytest.mark.smoke

OLLAMA_HOST = "localhost"
OLLAMA_PORT = 11434
EMBED_MODEL = "bge-m3"
EMBED_DIM = 1024


def _has_embed_model(name: str) -> bool:
    """True, wenn Ollama erreichbar ist und das Embedding-Modell gezogen wurde."""
    try:
        resp = httpx.get(f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags", timeout=2.0)
        resp.raise_for_status()
        # Ollama /api/tags liefert je nach Version "name" und/oder "model"
        # (z. B. "bge-m3:latest") — beide defensiv berücksichtigen.
        entries = resp.json().get("models", [])
        tags = [m.get("name") or m.get("model") for m in entries if isinstance(m, dict)]
        return any(tag and name in tag for tag in tags)
    except Exception:
        return False


async def test_ollama_embed_real() -> None:
    if not _has_embed_model(EMBED_MODEL):
        pytest.skip(f"Ollama/{EMBED_MODEL} nicht verfügbar — Embed-Smoke übersprungen")

    settings = EmbeddingSettings(
        _env_file=None,
        priority="ollama_only",
        model=EMBED_MODEL,
        dimension=EMBED_DIM,
        request_timeout_s=120.0,
    )
    provider = LocalEmbeddingProvider.from_settings(settings)
    vectors = await provider.embed(["Lager läuft heiß", "Spindel-Lager getauscht"])

    # Die Abstraktion lief real durch: ein Vektor je Text, Dimension passt auf
    # worker_notes.embedding vector(1024), L2-normiert (Cosine).
    assert len(vectors) == 2
    for vector in vectors:
        assert len(vector) == EMBED_DIM
        assert math.sqrt(sum(component * component for component in vector)) == pytest.approx(
            1.0, abs=1e-3
        )
