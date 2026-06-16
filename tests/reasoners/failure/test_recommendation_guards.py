# ============================================================
#  FOREMAN — tests/reasoners/failure/test_recommendation_guards.py
#  Zweck: Reine Unit-Tests der F-REC-Output-Guards (kein DB/LLM):
#         - detect_overclaim (Negativ-Guard, Invariante II): Treffer ohne Negation,
#           Erlaubnis bei Negation (False-Positive-Schutz), der deterministische
#           Caveat selbst ist sauber, und die DOKUMENTIERTE Distanz-Grenze der
#           20-Zeichen-Heuristik.
#         - Reihenfolge: der Guard MUSS auf dem sanitisierten Text laufen (sanitize
#           kann eine Overclaim-Phrase erst erzeugen) — so macht es der Service.
#         - sanitize_recommendation (LLM05) + extract_citations.
# ============================================================
from __future__ import annotations

from foreman.reasoners.failure.recommendation import (
    detect_overclaim,
    extract_citations,
    sanitize_recommendation,
)
from foreman.reasoners.failure.schema import validation_caveat_for


# --- detect_overclaim: Negativ-Guard (Invariante II) ---
def test_overclaim_phrase_ohne_negation_wird_erkannt() -> None:
    assert detect_overclaim("Das ist eine validierte Prognose.") is not None
    assert detect_overclaim("Der Ausfall ist sicher: garantierter Ausfall.") is not None


def test_overclaim_mit_negation_davor_erlaubt() -> None:
    # "keine/nicht ... validierte Prognose" ist KEINE Umdeutung → kein Reject
    # (False-Positive-Schutz für legitime Empfehlungen).
    assert detect_overclaim("Das ist keine validierte Prognose, nur eine Schätzung.") is None
    assert detect_overclaim("Dies ist nicht an realen Ausfällen validiert.") is None


def test_overclaim_deterministischer_caveat_ist_sauber() -> None:
    # Der deterministische Sim-Vorbehalt selbst darf NIE als Umdeutung gelten.
    assert detect_overclaim(validation_caveat_for("simulation_only")) is None


def test_overclaim_entfernte_negation_negiert_nicht() -> None:
    # Präziser Guard: nur das UNMITTELBAR vorangehende Wort zählt als Negation. Eine
    # entfernte Negation ("ohne Zweifel ... validierte Prognose", "kein Zweifel: ...")
    # deutet den Sim-Charakter trotzdem um → Treffer (kein False-Negative).
    assert detect_overclaim("Kein Zweifel: validierte Prognose.") is not None
    assert detect_overclaim("Ohne Zweifel eine validierte Prognose.") is not None


# --- LOW #6: der Guard MUSS auf dem sanitisierten Text laufen ---
def test_sanitize_kann_overclaim_phrase_erst_erzeugen() -> None:
    # Ein leerer Markdown-Link unterbricht die Phrase im Rohtext (Guard sieht sie nicht),
    # sanitize zieht die Tokens zusammen → die Phrase entsteht. Daher prüft der Service
    # detect_overclaim auf dem SANITISIERTEN Text (kein Post-Sanitize-Schlupf).
    roh = "Das ist eine validierte [](http://x)Prognose."
    assert detect_overclaim(roh) is None  # im Rohtext unterbrochen → nicht erkannt
    saniert = sanitize_recommendation(roh)
    assert detect_overclaim(saniert) is not None  # nach Sanitisierung erkannt


# --- sanitize_recommendation (LLM05) ---
def test_sanitize_entfernt_script_und_url_bewahrt_zitate() -> None:
    text = "Risiko [pred:1] <script>alert(1)</script> mehr unter http://evil.example."
    saniert = sanitize_recommendation(text)
    assert "<script" not in saniert.lower()
    assert "http://" not in saniert
    assert "[pred:1]" in saniert  # das Zitat bleibt erhalten


# --- extract_citations ---
def test_extract_citations_findet_alle_schemata_eindeutig() -> None:
    text = "[pred:1] und [factor:vibration_rms] und nochmal [pred:1] und [recall:0]."
    assert extract_citations(text) == ["pred:1", "factor:vibration_rms", "recall:0"]
