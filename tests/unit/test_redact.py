# ============================================================
#  FOREMAN — tests/unit/test_redact.py
#  Zweck: NER-Maskierung — Verdrahtung gegen einen gemockten Presidio-Analyzer
#         (kein 560-MB-spaCy-Modell in der Suite). Bezug: Research §5.3 (b).
# ============================================================
from __future__ import annotations

from unittest.mock import MagicMock

from foreman.core.redact import (
    DEFAULT_SCORE_THRESHOLD,
    PERSON_PLACEHOLDER,
    PresidioRedactor,
    build_redactor,
)


def test_redact_uses_injected_engines_and_returns_masked_text() -> None:
    analyzer = MagicMock()
    analyzer.analyze.return_value = ["<analyzer-result>"]
    anonymizer = MagicMock()
    anonymizer.anonymize.return_value = MagicMock(text="... mit [PERSON] getauscht")

    redactor = PresidioRedactor(analyzer=analyzer, anonymizer=anonymizer)
    out = redactor.redact_person_names("... mit Schmidt getauscht")

    assert out == "... mit [PERSON] getauscht"
    assert PERSON_PLACEHOLDER in out
    analyzer.analyze.assert_called_once()
    kwargs = analyzer.analyze.call_args.kwargs
    assert kwargs["entities"] == ["PERSON"]
    assert kwargs["language"] == "de"
    assert kwargs["score_threshold"] == DEFAULT_SCORE_THRESHOLD


def test_empty_text_is_passthrough_without_calling_engines() -> None:
    analyzer = MagicMock()
    anonymizer = MagicMock()
    redactor = PresidioRedactor(analyzer=analyzer, anonymizer=anonymizer)
    assert redactor.redact_person_names("") == ""
    analyzer.analyze.assert_not_called()


def test_custom_score_threshold_is_forwarded() -> None:
    analyzer = MagicMock()
    analyzer.analyze.return_value = []
    anonymizer = MagicMock()
    anonymizer.anonymize.return_value = MagicMock(text="x")
    redactor = PresidioRedactor(analyzer=analyzer, anonymizer=anonymizer, score_threshold=0.7)
    redactor.redact_person_names("x")
    assert analyzer.analyze.call_args.kwargs["score_threshold"] == 0.7


def test_build_redactor_returns_presidio_instance() -> None:
    assert isinstance(build_redactor(), PresidioRedactor)
