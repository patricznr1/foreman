# ============================================================
#  FOREMAN — tests/integration/test_redact_real.py
#  Zweck: Validiert die ECHTE NER-Maskierung (Presidio + spaCy de_core_news_lg)
#         gegen deutschen Freitext — fängt Regressionen in der Presidio-Config
#         (lang_code, Modellname, Entity-Label "PERSON", Threshold), die ein
#         gemockter Analyzer NICHT bemerken würde.
#  Opt-in (@pytest.mark.ner; im Default-Gate via `-m 'not ner'` deselektiert) UND
#  skip-if-absent: ohne installiertes ~560-MB-Modell wird sauber übersprungen,
#  ohne einen aussichtslosen Engine-Build zu versuchen.
#  Run: uv run python -m spacy download de_core_news_lg && uv run pytest -m ner
# ============================================================
from __future__ import annotations

import importlib.util

import pytest

from foreman.core.redact import PERSON_PLACEHOLDER, PresidioRedactor

_MODEL = "de_core_news_lg"


def _de_model_available() -> bool:
    """True, wenn spaCy installiert ist UND das de-Modell als Paket vorliegt."""
    if importlib.util.find_spec("spacy") is None:
        return False
    import spacy.util

    return bool(spacy.util.is_package(_MODEL))


pytestmark = [
    pytest.mark.ner,
    pytest.mark.skipif(
        not _de_model_available(), reason=f"spaCy-Modell {_MODEL} nicht installiert"
    ),
]


def test_real_presidio_masks_german_person_name() -> None:
    redactor = PresidioRedactor()
    masked = redactor.redact_person_names(
        "Lager an Spindel 3 mit Schmidt aus der Frühschicht getauscht"
    )
    assert "Schmidt" not in masked
    assert PERSON_PLACEHOLDER in masked


def test_real_presidio_keeps_text_without_names() -> None:
    redactor = PresidioRedactor()
    text = "Spindeltemperatur erhöht, Vorschub reduziert, läuft wieder stabil"
    assert redactor.redact_person_names(text) == text
