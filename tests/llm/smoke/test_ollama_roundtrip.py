# ============================================================
#  FOREMAN — tests/llm/smoke/test_ollama_roundtrip.py
#  Zweck: Echter Smoke-Round-Trip gegen lokales Ollama (F-LLM). Beweist, dass
#         die LLMGateway-Abstraktion real durchläuft (Prompt → Backend → Response)
#         — ohne CI/Default-Gate an Ollama zu koppeln: ist Ollama nicht erreichbar
#         oder kein Modell gezogen, wird SAUBER übersprungen (kein Fehler).
#  Architektur-Einordnung: Quality Gate §10.6 / Brief §6. @pytest.mark.smoke;
#         nicht im CI-Pflichtlauf. Nutzt das erste verfügbare Ollama-Modell.
# ============================================================
from __future__ import annotations

import httpx
import pytest

from foreman.llm.config import LLMSettings
from foreman.llm.gateway import LiteLLMGateway, Task

pytestmark = pytest.mark.smoke

OLLAMA_HOST = "localhost"
OLLAMA_PORT = 11434


def _ollama_models() -> list[str]:
    """Liefert die lokal gezogenen Ollama-Modelle (leer, wenn unerreichbar)."""
    try:
        resp = httpx.get(f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags", timeout=2.0)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return [m["name"] for m in models if "name" in m]
    except Exception:
        return []


async def test_ollama_roundtrip_real() -> None:
    models = _ollama_models()
    if not models:
        pytest.skip("Ollama nicht erreichbar oder kein Modell gezogen — Smoke übersprungen")

    # Erstes verfügbares Modell nutzen; Grounding aus (reiner Round-Trip-Beweis).
    settings = LLMSettings(
        _env_file=None,
        priority="local_only",
        local_model=f"ollama/{models[0]}",
        grounding_enabled=False,
        request_timeout_s=120.0,
    )
    gateway = LiteLLMGateway.from_settings(settings)
    resp = await gateway.complete(
        task=Task.EXPLANATION,
        system_prompt="Antworte sehr knapp auf Deutsch.",
        user_prompt="Antworte mit einem Wort: läuft der Round-Trip?",
    )

    # Die Abstraktion lief real durch: lokales Backend, nicht-leerer Text, Tokens gezählt.
    assert resp.backend == "local"
    assert resp.from_cache is False
    assert resp.text.strip() != ""
    assert resp.total_tokens >= 0
    assert resp.latency_ms >= 0.0
