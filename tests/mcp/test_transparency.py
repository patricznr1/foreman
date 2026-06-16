# ============================================================
#  FOREMAN — tests/mcp/test_transparency.py
#  Zweck: Den AI-Act-Transparenz-Wrapper (Art. 50(2), §10.5 Maßnahme 2) festnageln
#         — die Ehrlichkeit ist das Fundament: KI-Output trägt die Flags,
#         Vorhersage/Empfehlung tragen zusätzlich validation_status/data_regime,
#         Nicht-KI-Daten werden NICHT als KI gekennzeichnet.
#  Architektur-Einordnung: MCP-Schicht (F7). Reiner Wrapper-Test (keine DB).
# ============================================================
from __future__ import annotations

import pytest
from pydantic import ValidationError

from foreman.mcp.transparency import (
    GENERATED_BY,
    AiTransparency,
    ai_transparency,
    non_ai_transparency,
)


def test_generated_by_is_the_mandated_marker() -> None:
    """Der Erzeuger-Marker ist exakt 'foreman-ai' (§10.5 Maßnahme 2)."""
    assert GENERATED_BY == "foreman-ai"


def test_ai_prediction_envelope_carries_all_flags_and_validation() -> None:
    """KI-Vorhersage-Output trägt alle Art.-50(2)-Flags + validation_status/data_regime."""
    env = ai_transparency(
        model_version="lgbm-failure-2026.06",
        validation_status="simulation_only",
        data_regime="simulation",
        validation_caveat="Diese Einschätzung beruht auf simulierten Verläufen.",
    )
    assert env.ai_generated is True
    assert env.generated_by == "foreman-ai"
    assert env.requires_human_review is True
    assert env.model_version == "lgbm-failure-2026.06"
    assert env.validation_status == "simulation_only"
    assert env.data_regime == "simulation"
    assert env.validation_caveat is not None


def test_ai_envelope_without_persisted_model_version_is_honest_null() -> None:
    """KI-Output ohne persistierte Modell-Version (Ereignisketten): Flag da, Wert null."""
    env = ai_transparency(model_version=None)
    assert env.ai_generated is True
    assert env.generated_by == "foreman-ai"
    assert env.requires_human_review is True
    assert env.model_version is None
    # Ohne Sim-Vorbehalt-Kontext bleiben die Vorbehalts-Felder leer (ehrlich).
    assert env.validation_status is None
    assert env.data_regime is None
    assert env.validation_caveat is None


def test_non_ai_envelope_is_not_marked_as_ai() -> None:
    """Nicht-KI-Daten (Stammdaten/Readings/Alarme) tragen KEINE KI-Kennzeichnung."""
    env = non_ai_transparency()
    assert env.ai_generated is False
    assert env.generated_by is None
    assert env.requires_human_review is False
    assert env.model_version is None
    assert env.validation_status is None
    assert env.data_regime is None
    assert env.validation_caveat is None


def test_non_ai_envelope_may_not_smuggle_ai_fields() -> None:
    """Ein nicht als KI markierter Umschlag darf keine KI-Metadaten tragen (Ehrlichkeit)."""
    with pytest.raises(ValidationError):
        AiTransparency(ai_generated=False, model_version="x")
    with pytest.raises(ValidationError):
        AiTransparency(ai_generated=False, validation_status="simulation_only")
    with pytest.raises(ValidationError):
        AiTransparency(ai_generated=False, requires_human_review=True)


def test_ai_envelope_requires_consistent_marker_and_review_flag() -> None:
    """KI-Output muss generated_by='foreman-ai' UND requires_human_review=True tragen."""
    with pytest.raises(ValidationError):
        AiTransparency(
            ai_generated=True, generated_by="some-other-system", requires_human_review=True
        )
    with pytest.raises(ValidationError):
        AiTransparency(ai_generated=True, generated_by="foreman-ai", requires_human_review=False)


def test_envelope_is_frozen_and_forbids_extra_fields() -> None:
    """Der Umschlag ist unveränderlich und lässt kein Schmuggeln zusätzlicher Felder zu."""
    env = non_ai_transparency()
    with pytest.raises(ValidationError):
        AiTransparency(ai_generated=False, sneaky_field="x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        env.ai_generated = True  # type: ignore[misc]
