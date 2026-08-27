# ============================================================
#  FOREMAN — tests/unit/test_redact.py
#  Zweck: NER-Maskierung — Verdrahtung gegen einen gemockten Presidio-Analyzer
#         (kein 560-MB-spaCy-Modell in der Suite). Bezug: Research §5.3 (b).
# ============================================================
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from foreman.core.redact import (
    DEFAULT_SCORE_THRESHOLD,
    FACHBEGRIFFE,
    PERSON_PLACEHOLDER,
    PresidioRedactor,
    build_redactor,
)


def _treffer(start: int, ende: int) -> SimpleNamespace:
    """Eine Attrappe in der Form, die Presidio wirklich liefert.

    `analyze` gibt `RecognizerResult`-Objekte mit `start`/`end` zurück, keine
    Zeichenketten. Die frühere Attrappe lieferte einen String — sie hätte jede
    Änderung überstanden, die auf den Spann-Grenzen arbeitet, und genau eine
    solche kam am 27.08.2026 dazu (der Fachsprache-Filter). Eine Attrappe, die
    weniger kann als die echte Schnittstelle, prüft weniger als sie soll.
    """
    return SimpleNamespace(start=start, end=ende)


def test_redact_uses_injected_engines_and_returns_masked_text() -> None:
    analyzer = MagicMock()
    # "Schmidt" in "... mit Schmidt getauscht"
    analyzer.analyze.return_value = [_treffer(8, 15)]
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


# ──────────────────────────────────────────────────────────────────────
#  Falschtreffer auf Hallensprache (Befund 27.08.2026)
#
#  An 327 echten Instandhaltungs-Texten gemessen: Das Modell hält deutsche
#  Fachkomposita für Personennamen und ist sich dabei GENAU SO SICHER wie bei
#  echten Namen — "Klemmer", "Nachtschicht" und "Energiekette" bekommen 0,85,
#  "Thomas Weber" ebenfalls. Die Schwelle trennt das nicht.
#
#  Ersetzt wurde dabei der BEFUND: aus "Niederhalterfeder gebrochen" wurde
#  "[PERSON] gebrochen" — der Satz verlor genau das Wort, wegen dessen ihn
#  jemand später sucht. 90 von 327 Texten betroffen, bei den Wartungen 77 von 124.
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "span",
    ["Energiekette", "Niederhalterfeder", "Nachtschicht", "Regelintervall", "Klemmnabe"],
)
def test_fachbegriff_gilt_nicht_als_name(span: str) -> None:
    """Belegte Fachbegriffe werden aussortiert — sie tragen den Befund."""
    assert PresidioRedactor._ist_fachsprache(span) is True


@pytest.mark.parametrize(
    "span",
    ["FD-01.", "AX-04. Schmierstoff", "Werkzeugwechsel PR-02.", "Regelprüfung Hydraulik PR-03."],
)
def test_treffer_mit_ziffer_gilt_nicht_als_name(span: str) -> None:
    """Ein Personenname enthält keine Ziffer — strukturell, nicht heuristisch.

    Das Modell zieht Maschinenkennungen in den Treffer hinein. Solche Spans
    lassen sich verlustfrei verwerfen.
    """
    assert PresidioRedactor._ist_fachsprache(span) is True


@pytest.mark.parametrize("span", ["Thomas Weber", "Weber", "Müller", "Anna Schmidt", "Özdemir"])
def test_echter_name_faellt_weiterhin(span: str) -> None:
    """Der Filter darf keinen Namen durchlassen, der vorher maskiert wurde."""
    assert PresidioRedactor._ist_fachsprache(span) is False


def test_fachwort_versteckt_keinen_namen() -> None:
    """AUFBAU-KONTROLLE: Ein Treffer mit EINEM unbekannten Wort bleibt ein Name.

    Ohne diese Bedingung liesse sich ein echter Name hinter einem Fachbegriff
    verstecken — der Filter würde die ganze Spanne verwerfen und den Namen
    stehen lassen. Das wäre die schlimmste denkbare Wirkung dieser Änderung:
    ein Datenschutz-Verlust, eingeführt von einer Verbesserung der Lesbarkeit.
    """
    assert PresidioRedactor._ist_fachsprache("Nachschmierung Weber") is False
    assert PresidioRedactor._ist_fachsprache("Regelintervall Schmidt") is False


@pytest.mark.parametrize("wort", ["scheibe", "feder", "span", "kühler", "trichter", "ventil"])
def test_moegliche_familiennamen_stehen_bewusst_nicht_in_der_liste(wort: str) -> None:
    """Diese Fachbegriffe sind zugleich deutsche Nachnamen — und bleiben draussen.

    Ein Werker, der Scheibe oder Feder heisst, würde sonst nie maskiert. Die
    Falschtreffer auf diesen Wörtern bleiben deshalb bestehen; das ist der
    bewusst gezahlte Preis, keine Lücke.

    Der Test nagelt die Entscheidung fest: Wer eines dieser Wörter aufnimmt,
    ändert ihn wissentlich mit — statt die Liste stillschweigend zu erweitern,
    weil ein Text „unschön" maskiert wurde.
    """
    assert wort not in FACHBEGRIFFE


def test_leerer_treffer_gilt_nicht_als_fachsprache() -> None:
    """Sonst würde ein leerer Span alles durchlassen, was der Filter sieht."""
    assert PresidioRedactor._ist_fachsprache("") is False
    assert PresidioRedactor._ist_fachsprache("   ") is False
