# ============================================================
#  FOREMAN — config.py
#  Zweck: Zentrale Konfiguration aus Umgebungsvariablen (Pydantic-Settings).
#  Architektur-Einordnung: Querschnitt (Schicht 2). Einzige Quelle für
#         DB-, Auth-, Substrat- und Pseudonymisierungs-Parameter.
#  Sicherheit (§8): Secrets ausschließlich aus der gitignorten .env /
#         dem Secret-Store — niemals im Repo (Repo ist öffentlich).
# ============================================================
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Unsicherer JWT-Default — nur Platzhalter; im Produktionsbetrieb hart abgelehnt.
INSECURE_JWT_SECRET = "change-me-in-env"
# Mindest-Entropie für HS256 (RFC 7518 §3.2).
_JWT_SECRET_MIN_BYTES = 32
# Umgebungen, in denen ein schwaches Secret toleriert wird (lokale Entwicklung/Tests).
_DEV_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "testing"})


class Settings(BaseSettings):
    """Anwendungs-Konfiguration. Wird einmalig aus der Umgebung geladen."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # --- App ---
    app_name: str = "FOREMAN"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # --- Datenbank (async SQLAlchemy 2.0 / asyncpg) ---
    # Beispiel: postgresql+asyncpg://foreman:<pw>@localhost:5432/foreman
    database_url: str = "postgresql+asyncpg://foreman:foreman@localhost:5432/foreman"
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_echo: bool = False

    # --- Auth / JWT ---
    jwt_secret: str = INSECURE_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # --- Gedächtnis-Substrat (NEXUS-Anbindung, §9) ---
    # Base-URL + Token aus der .env. Datenaufnahme läuft auch ohne Substrat (Fallback).
    substrate_base_url: str | None = None
    substrate_token: str | None = None
    substrate_timeout_s: float = 10.0
    substrate_namespace: str = "foreman"
    # Endpunkt-Pfade konfigurierbar (Default = generischer REST-Vertrag).
    substrate_remember_path: str = "/remember"
    substrate_recall_path: str = "/recall"
    substrate_reason_path: str = "/reason"
    substrate_drift_status_path: str = "/drift_status"
    substrate_reflect_path: str = "/reflect"

    # --- Pseudonymisierung (HMAC, §8 / Research §5.3 a) ---
    # Werte aus der .env: FOREMAN_PSEUDO_KEY_VERSION, FOREMAN_PSEUDO_KEY_VERSIONS,
    # FOREMAN_PSEUDO_KEY_<version> (32-Byte-Hex je Version).
    pseudo_key_version: str = Field(default="v1", validation_alias="FOREMAN_PSEUDO_KEY_VERSION")
    pseudo_key_versions: str = Field(default="v1", validation_alias="FOREMAN_PSEUDO_KEY_VERSIONS")
    pseudo_tenant: str = Field(default="default", validation_alias="FOREMAN_PSEUDO_TENANT")

    # --- Archiv-Suche: Relevanz-Cutoff der hybriden Notiz-Suche (§15) ---
    # Maximal zulässige Cosine-Distanz, ab der ein REINER Vektor-Treffer (ohne
    # Volltext-Match) verworfen wird — der Riegel gegen semantisch-vages Auffüllen.
    # Ein Kandidat bleibt nur, wenn er einen Volltext-Match hat ODER seine Distanz
    # unter dieser Schwelle liegt. Bereich der Cosine-Distanz bei L2-normierten
    # Vektoren: 0 (identisch) … 2 (entgegengesetzt); konservativer Start 0.55, auf
    # Realdaten ohne Redeploy justierbar (kleiner = strenger).
    archive_vector_max_distance: float = Field(
        default=0.55,
        ge=0.0,
        le=2.0,
        validation_alias="FOREMAN_ARCHIVE_VECTOR_MAX_DISTANCE",
    )

    @property
    def is_production(self) -> bool:
        """True, wenn die Umgebung NICHT als Entwicklung/Test markiert ist."""
        return self.environment.lower() not in _DEV_ENVIRONMENTS

    def require_secure_secrets(self) -> None:
        """Bricht im Produktionsbetrieb ab, wenn das JWT-Secret schwach/Default ist.

        Schützt davor, dass FOREMAN versehentlich mit dem öffentlich bekannten
        Platzhalter-Secret hochfährt (Repo ist öffentlich → jeder könnte sonst
        gültige Tokens fälschen). In Entwicklung/Tests bleibt der Default erlaubt.
        """
        if not self.is_production:
            return
        too_short = len(self.jwt_secret.encode("utf-8")) < _JWT_SECRET_MIN_BYTES
        if self.jwt_secret == INSECURE_JWT_SECRET or too_short:
            raise RuntimeError(
                "❌ JWT_SECRET ist im Produktionsbetrieb nicht sicher gesetzt "
                f"(mindestens {_JWT_SECRET_MIN_BYTES} Byte erforderlich, kein Default). "
                "Bitte JWT_SECRET in der .env/im Secret-Store setzen."
            )

    def pseudo_keys(self) -> dict[str, bytes]:
        """Lädt die versionierten HMAC-Schlüssel aus der Umgebung.

        Format je Version: FOREMAN_PSEUDO_KEY_<version> = 32-Byte-Hex.
        Fehlende/leere Schlüssel werden übersprungen — der Pseudonymizer
        meldet beim Fehlen der aktiven Version selbst einen klaren Fehler.
        """
        keys: dict[str, bytes] = {}
        for version in (v.strip() for v in self.pseudo_key_versions.split(",")):
            if not version:
                continue
            raw = os.environ.get(f"FOREMAN_PSEUDO_KEY_{version}")
            if raw:
                keys[version] = bytes.fromhex(raw)
        return keys


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Liefert die (einmalig geladene) Konfiguration. Als FastAPI-Dependency nutzbar."""
    return Settings()
