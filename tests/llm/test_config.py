# ============================================================
#  FOREMAN — tests/llm/test_config.py
#  Zweck: Pflicht-Test-Block für die LLM-Settings (F-LLM). Prüft: Defaults
#         (lokal-first, Qwen3/Ollama, Grounding an, Cache aus), env-Prefix-
#         Override, SecretStr-Leak-Schutz (§8: Keys nie im Klartext), Priority-
#         Literal-Validierung, gecachter Getter.
#  Architektur-Einordnung: Quality Gate §10.3. Reine Unit-Tests, kein Netz.
# ============================================================
from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from foreman.llm.config import LLMSettings, get_llm_settings


def test_defaults_sind_lokal_first_qwen_grounding_an_cache_aus() -> None:
    s = LLMSettings(_env_file=None)
    assert s.priority == "local_first"
    assert "qwen" in s.local_model.lower()
    assert s.local_base_url.startswith("http")
    assert s.grounding_enabled is True
    assert s.cache_enabled is False
    # Lokale Inferenz ist kostenlos (Kosten-Schätzung pro Backend, §11.1).
    assert s.local_cost_per_1k_tokens == 0.0


def test_secretstr_leakt_den_key_nicht_im_repr() -> None:
    s = LLMSettings(_env_file=None, cloud_api_key="sk-streng-geheim-123")
    assert isinstance(s.cloud_api_key, SecretStr)
    # Weder das Settings-Repr noch das SecretStr-Repr zeigen den Klartext (§8).
    assert "sk-streng-geheim-123" not in repr(s)
    assert "sk-streng-geheim-123" not in str(s.cloud_api_key)
    # Der echte Wert ist nur über den expliziten Getter erreichbar.
    assert s.cloud_api_key.get_secret_value() == "sk-streng-geheim-123"


def test_priority_literal_lehnt_unbekannten_modus_ab() -> None:
    with pytest.raises(ValidationError):
        LLMSettings(_env_file=None, priority="magic")  # type: ignore[arg-type]


def test_env_prefix_ueberschreibt_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOREMAN_LLM_PRIORITY", "cloud_only")
    monkeypatch.setenv("FOREMAN_LLM_CLOUD_API_KEY", "sk-from-env")
    s = LLMSettings(_env_file=None)
    assert s.priority == "cloud_only"
    assert s.cloud_api_key is not None
    assert s.cloud_api_key.get_secret_value() == "sk-from-env"


def test_get_llm_settings_ist_gecacht() -> None:
    a = get_llm_settings()
    b = get_llm_settings()
    assert a is b
