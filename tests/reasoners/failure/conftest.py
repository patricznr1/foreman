# ============================================================
#  FOREMAN — tests/reasoners/failure/conftest.py
#  Zweck: Geteilte Fixtures der F-PRED-Tests — lädt das gebündelte
#         Demonstrator-Artefakt EINMAL je Session (SHAP-Explainer ist teuer).
# ============================================================
from __future__ import annotations

import pytest

from foreman.reasoners.failure.model import DEFAULT_ARTIFACT_PATH, FailureModel, load_model


@pytest.fixture(scope="session")
def failure_model() -> FailureModel:
    """Das gebündelte F-PRED-Artefakt (auf Simulationsdaten trainiert, §16)."""
    return load_model(DEFAULT_ARTIFACT_PATH)
