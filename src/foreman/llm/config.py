# ============================================================
#  FOREMAN — llm/config.py
#  Zweck: Konfiguration des Modell-Gateways (F-LLM) aus Umgebungsvariablen
#         (Pydantic-Settings, F2-Muster erweitert). Backend-URLs, Modellnamen,
#         Priority-Modus, Timeouts, Rate-Limits, API-Keys (SecretStr),
#         Grounding-Policy, Caching, Kosten-Sätze pro Backend.
#  Architektur-Einordnung: Querschnitt der LLM-Schicht (Schicht 2). Einzige
#         Quelle der Gateway-Parameter; vom LiteLLMGateway über `from_settings`
#         konsumiert.
#  Sicherheit (§8): API-Keys als SecretStr — niemals im Klartext loggen.
#         Werte ausschließlich aus der gitignorten .env / dem Secret-Store.
# ============================================================
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Priority-Modus der Backend-Auswahl (GROUND_TRUTH §13, F-LLM-Vertrag).
# local_first : lokal zuerst, Cloud als Fallback (Default — lokal-first-Prinzip).
# cloud_first : Cloud zuerst, lokal als Fallback.
# local_only  : ausschließlich lokal — kein Cloud-Fallback (Air-Gap/Datenschutz).
# cloud_only  : ausschließlich Cloud — kein lokales Backend.
Priority = Literal["local_first", "cloud_first", "local_only", "cloud_only"]


class LLMSettings(BaseSettings):
    """Konfiguration des Modell-Gateways. Einmalig aus der Umgebung geladen.

    Alle Variablen tragen den Präfix `FOREMAN_LLM_` (z. B.
    `FOREMAN_LLM_PRIORITY=cloud_only`, `FOREMAN_LLM_CLOUD_API_KEY=...`).
    """

    model_config = SettingsConfigDict(
        env_prefix="FOREMAN_LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Routing ---
    priority: Priority = "local_first"

    # --- Lokales Backend (Ollama, Dev-/Showcase-Default: Qwen3-14B, Apache 2.0) ---
    local_base_url: str = "http://localhost:11434"
    local_model: str = "ollama/qwen3:14b"
    # Supply-Chain-Integrität (LLM03/04, §10.4): optionaler Modell-Digest-Pin.
    # Keine Auflösung/Erzwingung zur Laufzeit gebaut — nur dokumentiert/durchgereicht.
    local_model_digest: str | None = None
    # Lokale Inferenz ist kostenlos (Kosten-Schätzung pro Backend, §11.1).
    local_cost_per_1k_tokens: float = 0.0

    # --- Cloud-Backend (Anthropic-Fallback über LiteLLM) ---
    cloud_model: str = "anthropic/claude-sonnet-4-5"
    cloud_api_key: SecretStr | None = None
    # Kosten-Schätzung Cloud: getrennt für Eingabe/Ausgabe (USD je 1k Tokens).
    cloud_input_cost_per_1k: float = 0.003
    cloud_output_cost_per_1k: float = 0.015

    # --- Aufruf-Parameter ---
    request_timeout_s: float = 60.0
    temperature: float = 0.0
    max_tokens: int | None = None

    # --- Rate-Limit (Token-Bucket pro Backend, OWASP LLM10, §11.2) ---
    rate_limit_capacity: int = Field(default=60, ge=1)
    rate_limit_refill_per_s: float = Field(default=1.0, gt=0.0)

    # --- Grounding-Policy (Spotlighting + Quellenbindung) ---
    grounding_enabled: bool = True
    # strikt = unbelegter Output wirft GroundingViolation; sonst nur Report.
    grounding_strict: bool = False

    # --- Deterministisches Antwort-Caching (Tests: Byte-Determinismus) ---
    cache_enabled: bool = False


@lru_cache(maxsize=1)
def get_llm_settings() -> LLMSettings:
    """Liefert die (einmalig geladene) LLM-Konfiguration. Als Dependency nutzbar."""
    return LLMSettings()
