# ============================================================
#  FOREMAN — llm/errors.py
#  Zweck: Fehlerhierarchie des Modell-Gateways (F-LLM). Die einzige
#         Fehler-Schnittstelle, die ein Reasoner je fängt — keine LiteLLM-
#         Ausnahme dringt nach oben durch (Architektur-Grenze des Briefings).
#  Architektur-Einordnung: Querschnitt der LLM-Schicht (Schicht 2). Vorbild
#         ist der SubstrateClient (§9): typisierte, deutschsprachige Fehler
#         statt durchgereichter Library-Ausnahmen.
#  Konvention (§6): Fehlermeldungen auf Deutsch; keine PII in Meldungen.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence


class GatewayError(RuntimeError):
    """Basis aller Gateway-Fehler.

    Ein Reasoner kann mit einem einzigen ``except GatewayError`` jede
    Fehlersituation des Gateways behandeln, ohne LiteLLM-Interna zu kennen.
    """


class GatewayConfigError(GatewayError):
    """Fehlkonfiguration des Gateways (z. B. cloud_only ohne API-Key)."""


class BackendUnavailable(GatewayError):
    """Kein erlaubtes Backend erreichbar — Fallback verboten oder erschöpft.

    `attempted` listet die in Prioritäts-Reihenfolge erfolglos versuchten
    Backends (für Logging/Observability, keine PII).
    """

    def __init__(self, message: str, *, attempted: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.attempted: tuple[str, ...] = tuple(attempted)


class RateLimited(GatewayError):
    """Token-Bucket eines Backends erschöpft (OWASP LLM10).

    `retry_after_s` gibt an, nach wie vielen Sekunden frühestens wieder ein
    Token verfügbar ist (Schätzung aus der Refill-Rate).
    """

    def __init__(self, message: str, *, retry_after_s: float = 0.0) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class GroundingViolation(GatewayError):
    """Die Antwort führt unbelegte Entitäten/Zahlen ein (Grounding-Bruch).

    `unbacked` enthält die im Output gefundenen, durch keine Quelle gedeckten
    Tokens (z. B. fabrizierte Zahlen). Wird bei strikter Grounding-Policy
    hochgereicht; sonst nur im Grounding-Report vermerkt.
    """

    def __init__(self, message: str, *, unbacked: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.unbacked: list[str] = list(unbacked)


class GatewayTimeout(GatewayError):
    """Zeitüberschreitung beim Backend-Aufruf (Timeout-Guard, §11.2)."""
