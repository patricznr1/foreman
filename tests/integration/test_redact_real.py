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


# ──────────────────────────────────────────────────────────────────────
#  Hallensprache bleibt stehen (Befund 27.08.2026)
#
#  An 327 echten Instandhaltungs-Texten gemessen: Das Modell hält deutsche
#  Fachkomposita für Personennamen und ist sich dabei GENAU SO SICHER wie bei
#  echten Namen — "Klemmer", "Nachtschicht" und "Energiekette" bekommen 0,85,
#  "Thomas Weber" ebenfalls. Die Schwelle kann das nicht trennen.
#
#  DIESE FÄLLE BRAUCHEN DAS ECHTE MODELL. Eine Attrappe würde sie nicht fangen:
#  Sie prüfen nicht den Filter (das tun die Einheitstests), sondern ob der
#  Filter am ECHTEN Erkenner das Richtige tut.
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "Prüfung AX-01 auf Laufgeräusch. Führung und Lager ohne Befund. "
        "Energiekette hatte Kontakt zur Verkleidung.",
        "Prüfung Fügewerkzeug PR-02 auf Meldung aus der Endkontrolle. Niederhalterfeder gebrochen.",
        "FD-02 macht den Klemmer doppelt so langsam zu wie FD-01.",
        "AX-04 hat heute Nacht die Position verloren. Nachtschicht hat nichts dazu geschrieben.",
    ],
)
def test_der_befund_bleibt_im_text(text: str) -> None:
    """Der Wortlaut wird nicht angetastet, wo kein Name steht.

    Ersetzt wurde vorher der BEFUND: aus „Niederhalterfeder gebrochen" wurde
    „[PERSON] gebrochen" — der Satz verlor genau das Wort, wegen dessen ihn
    jemand später sucht. Für eine Suche über Instandhaltungstexte ist das der
    teuerste denkbare Verlust.
    """
    assert PresidioRedactor().redact_person_names(text) == text


def test_echter_name_faellt_auch_neben_fachsprache() -> None:
    """AUFBAU-KONTROLLE am echten Modell: Der Filter darf nichts durchlassen.

    Ohne diese Zusicherung wäre die Verbesserung der Lesbarkeit zugleich ein
    Datenschutz-Verlust — ein Name, der sich hinter einem Fachbegriff versteckt.
    """
    text = "Nachschmierung Gelenklager mit Thomas Weber besprochen, Regelintervall bleibt."
    maskiert = PresidioRedactor().redact_person_names(text)
    assert "Weber" not in maskiert
    assert PERSON_PLACEHOLDER in maskiert
    # Und die Fachbegriffe stehen weiterhin da.
    assert "Gelenklager" in maskiert
    assert "Regelintervall" in maskiert
