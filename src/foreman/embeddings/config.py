# ============================================================
#  FOREMAN — embeddings/config.py
#  Zweck: Konfiguration der Embedding-Schicht (F-SEM) aus Umgebungsvariablen
#         (Pydantic-Settings, F2-/F-LLM-Muster). Backend-Wahl + Priority/Fallback,
#         Modellnamen, Vektor-Dimension, L2-Normalisierung, lokale Ollama-URL,
#         Timeout, Batch-Größe.
#  Architektur-Einordnung: Querschnitt der Embedding-Schicht (Schicht 2). Einzige
#         Quelle der Provider-Parameter; vom LocalEmbeddingProvider über
#         `from_settings` konsumiert. Parallele, gleich geformte Schicht zum
#         LLM-Gateway (§13) — Embeddings sind ein anderer Pfad als Completion.
#  Sicherheit (§8): keine Secrets nötig (lokale Inferenz); Werte aus der .env.
# ============================================================
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Priority-Modus der Backend-Auswahl (analog LLM-Gateway §13). Beide Backends sind
# lokal (kein Cloud-Embedding): Ollama (bge-m3, Dev-/Showcase-Default, derselbe
# Inferenz-Stack wie das LLM) und sentence-transformers als Alternative.
# ollama_first : Ollama zuerst, sentence-transformers als Fallback (Default).
# st_first     : sentence-transformers zuerst, Ollama als Fallback.
# ollama_only  : ausschließlich Ollama — kein Fallback.
# st_only      : ausschließlich sentence-transformers — kein Fallback.
Priority = Literal["ollama_first", "st_first", "ollama_only", "st_only"]

# Backend-Namen (niedrig-kardinale Metrik-Labels, keine Library-Typen nach außen).
OLLAMA_BACKEND = "ollama"
ST_BACKEND = "sentence_transformers"


class EmbeddingSettings(BaseSettings):
    """Konfiguration der Embedding-Schicht. Einmalig aus der Umgebung geladen.

    Alle Variablen tragen den Präfix `FOREMAN_EMBED_` (z. B.
    `FOREMAN_EMBED_PRIORITY=ollama_only`, `FOREMAN_EMBED_DIMENSION=1024`).
    """

    model_config = SettingsConfigDict(
        env_prefix="FOREMAN_EMBED_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Routing ---
    priority: Priority = "ollama_first"

    # --- Lokales Ollama-Backend (Default: bge-m3, MIT, 1024-dim, stark auf Deutsch) ---
    local_base_url: str = "http://localhost:11434"
    model: str = "bge-m3"

    # --- sentence-transformers-Alternative (gleiche Schnittstelle, lazy geladen) ---
    # Modell-Repo-Name (HF); CPU-Default, damit kein GPU-Zwang im API-Prozess.
    st_model: str = "BAAI/bge-m3"
    st_device: str = "cpu"

    # --- Vektor-Form (muss 1:1 auf worker_notes.embedding vector(1024) passen) ---
    dimension: int = Field(default=1024, ge=1)
    # L2-Normalisierung erzwingen (Cosine-Distanz im HNSW-Index erwartet normierte Vektoren).
    normalize: bool = True

    # --- Aufruf-Parameter ---
    request_timeout_s: float = Field(default=30.0, gt=0.0)
    # Batch-Größe für Ingestion-/Backfill-Embedding (ein Batch-Call statt pro Notiz).
    batch_size: int = Field(default=32, ge=1)


@lru_cache(maxsize=1)
def get_embedding_settings() -> EmbeddingSettings:
    """Liefert die (einmalig geladene) Embedding-Konfiguration. Als Dependency nutzbar."""
    return EmbeddingSettings()
