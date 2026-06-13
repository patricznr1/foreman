# ============================================================
#  FOREMAN — core/pseudonymize.py
#  Zweck: Deterministische HMAC-SHA-256-Tokenisierung werkerbezogener IDs.
#  Architektur-Einordnung: Datenschutz-Schreibpfad (Schicht 2). Genutzt von
#         worker_notes.author, alarms.acknowledged_by, maintenance_events.performed_by.
#  Verbindliche Referenz: docs/research/anonymisierung-werkerdaten.md §5.3 (a).
#  Prinzip (§8): Klartext-Identität nur in `users`; die Nutzdatenbank speichert
#         ausschließlich Token "v{n}:{64-hex}". Re-Identifikation kontrolliert
#         über verify_token gegen ein bekanntes user_id.
# ============================================================
from __future__ import annotations

import hashlib
import hmac

from foreman.config import Settings


class PseudonymizationError(RuntimeError):
    """Fehler in der Schlüsselverwaltung der Pseudonymisierung (Deutsch, §6)."""


class Pseudonymizer:
    """Schlüsselgebundene, deterministische Tokenisierung mit Key-Versionierung.

    - Gebunden an user_id (nicht den Klartext-Namen): stabil über Namensänderungen.
    - tenant als kontextgebundener Salt: gleiche ID → je Mandant anderes Token
      (verhindert mandantenübergreifende Verknüpfung).
    - Key-Version im Präfix: erlaubt Rotation ohne Verlust der Lesbarkeit alter Token.
    """

    def __init__(
        self,
        *,
        active_version: str,
        keys: dict[str, bytes],
        tenant: str = "default",
    ) -> None:
        if active_version not in keys:
            raise PseudonymizationError(
                f"Aktive Schlüssel-Version '{active_version}' fehlt im Schlüsselbund. "
                "Bitte FOREMAN_PSEUDO_KEY_* in der .env setzen."
            )
        self._active_version = active_version
        self._keys = keys
        self._tenant = tenant

    def tokenize_worker(self, user_id: str, *, tenant: str | None = None) -> str:
        """Deterministisches, schlüsselgebundenes Pseudonym für eine Werker-ID."""
        key = self._keys[self._active_version]
        msg = f"{tenant or self._tenant}:{user_id}".encode()
        digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
        return f"{self._active_version}:{digest}"

    def verify_token(self, user_id: str, token: str, *, tenant: str | None = None) -> bool:
        """Prüft ein bekanntes user_id gegen ein Token (gezielte, berechtigte Re-ID).

        Nutzt die im Token kodierte Key-Version, damit auch vor einer Rotation
        erzeugte Token weiterhin verifizierbar bleiben.
        """
        try:
            version, _ = token.split(":", 1)
            key = self._keys[version]
        except (ValueError, KeyError):
            return False
        msg = f"{tenant or self._tenant}:{user_id}".encode()
        expected = f"{version}:{hmac.new(key, msg, hashlib.sha256).hexdigest()}"
        return hmac.compare_digest(expected, token)  # zeitkonstanter Vergleich


def build_pseudonymizer(settings: Settings) -> Pseudonymizer:
    """Baut den Pseudonymizer aus der Config (Schlüssel aus der Umgebung)."""
    return Pseudonymizer(
        active_version=settings.pseudo_key_version,
        keys=settings.pseudo_keys(),
        tenant=settings.pseudo_tenant,
    )
