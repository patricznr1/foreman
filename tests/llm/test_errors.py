# ============================================================
#  FOREMAN — tests/llm/test_errors.py
#  Zweck: Pflicht-Test-Block für die Fehlerhierarchie des Modell-Gateways
#         (F-LLM). Prüft: gemeinsame Basis, typisierte Felder (retry_after_s,
#         attempted, unbacked), deutsche Meldungen (§6).
#  Architektur-Einordnung: Quality Gate §10.3. Reine Unit-Tests, kein Netz.
# ============================================================
from __future__ import annotations

import pytest

from foreman.llm.errors import (
    BackendUnavailable,
    GatewayConfigError,
    GatewayError,
    GatewayTimeout,
    GroundingViolation,
    RateLimited,
)


def test_alle_gateway_fehler_teilen_eine_basis() -> None:
    # Reasoner sollen mit einem einzigen `except GatewayError` alles fangen können.
    for exc_type in (
        GatewayConfigError,
        BackendUnavailable,
        RateLimited,
        GroundingViolation,
        GatewayTimeout,
    ):
        assert issubclass(exc_type, GatewayError)
    # GatewayError ist ein RuntimeError (Muster wie SubstrateError, §9).
    assert issubclass(GatewayError, RuntimeError)


def test_rate_limited_traegt_retry_after() -> None:
    exc = RateLimited("zu viele Anfragen", retry_after_s=2.5)
    assert exc.retry_after_s == 2.5
    assert "Anfragen" in str(exc)


def test_backend_unavailable_traegt_versuchte_backends() -> None:
    exc = BackendUnavailable("alle Backends nicht erreichbar", attempted=("local", "cloud"))
    assert exc.attempted == ("local", "cloud")


def test_grounding_violation_traegt_unbelegte_entitaeten() -> None:
    exc = GroundingViolation("unbelegte Zahlen im Output", unbacked=["999", "42"])
    assert exc.unbacked == ["999", "42"]


def test_gateway_error_faengt_subklassen() -> None:
    with pytest.raises(GatewayError):
        raise GatewayTimeout("Zeitüberschreitung beim Backend")
