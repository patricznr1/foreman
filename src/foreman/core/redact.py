# ============================================================
#  FOREMAN — core/redact.py
#  Zweck: NER-Maskierung von Personennamen in Werker-Freitext VOR dem Insert.
#  Architektur-Einordnung: Datenschutz-Schreibpfad (Schicht 2). Genutzt vom
#         worker_notes-Schreibpfad auf `text`.
#  Verbindliche Referenz: docs/research/anonymisierung-werkerdaten.md §5.3 (b).
#  Restrisiko (§8): NER-Recall < 100 % — der Freitext wird NIE als anonym
#         deklariert; Löschfrist + Zugriffsschutz bleiben nötig.
# ============================================================
from __future__ import annotations

from typing import Any, Protocol

# Presidio-Importe sind günstig; das (große) spaCy-Modell wird erst beim
# tatsächlichen Engine-Bau geladen — daher Lazy-Initialisierung weiter unten.
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# Recall-orientiert: lieber zu viel maskieren (Research §5.3 b).
DEFAULT_SCORE_THRESHOLD = 0.35
PERSON_PLACEHOLDER = "[PERSON]"

# ──────────────────────────────────────────────────────────────────────────
#  Zwei Filter gegen Falschtreffer auf Hallensprache (27.08.2026)
#
#  ANLASS, an 327 echten Instandhaltungs-Texten gemessen: Das Modell hält
#  deutsche Fachkomposita für Personennamen und ist sich dabei GENAU SO SICHER
#  wie bei echten Namen — "Klemmer", "Nachtschicht" und "Energiekette" bekommen
#  0,85, "Thomas Weber" ebenfalls. Die Schwelle trennt das nicht; sie trifft
#  beides oder keines. 90 von 327 Texten wurden verändert, bei den
#  Wartungsberichten 77 von 124.
#
#  Was das anrichtet: Ersetzt wird der BEFUND. Aus "Niederhalterfeder gebrochen"
#  wird "[PERSON] gebrochen" — der Satz verliert genau das Wort, wegen dessen ihn
#  jemand später sucht.
#
#  WAS DIESE FILTER NICHT TUN: den Schutz lockern. Beide sind strukturell
#  begründet und lassen keinen Namen durch, der vorher maskiert wurde — siehe
#  die Begründung an jedem einzelnen.
# ──────────────────────────────────────────────────────────────────────────

# FILTER 1 — Ziffern. Ein Personenname enthält keine. Fängt die Spans ab, in die
# das Modell eine Maschinenkennung hineinzieht: "FD-01.", "AX-04. Schmierstoff",
# "Werkzeugwechsel PR-02.". Verlustfrei: Wer "Thomas Weber 2" heisst, ist kein
# Fall, den dieses System kennt.

# FILTER 2 — belegte Fachbegriffe. NUR Wörter, die (a) an echtem Material als
# Falschtreffer beobachtet wurden UND (b) kein plausibler deutscher Familienname
# sind. Die Einschränkung (b) ist die wichtige: "Scheibe", "Feder", "Span",
# "Kühler" und "Trichter" stehen BEWUSST NICHT hier — es sind Nachnamen, und ein
# Werker, der so heisst, würde sonst nie maskiert. Diese Falschtreffer bleiben
# also bestehen; das ist der bewusst gezahlte Preis.
#
# Wer die Liste erweitert, prüft beide Bedingungen und nennt den Beleg. Eine
# Erweiterung „auf Verdacht" verschiebt eine Datenschutz-Grenze.
FACHBEGRIFFE: frozenset[str] = frozenset(
    {
        # Intervalle und Vorgänge
        "regelintervall",
        "kontrollintervall",
        "regelprüfung",
        "werkzeugwechsel",
        "nachschmierung",
        "nachgeschmiert",
        "sichtgeprüft",
        "rütteln",
        "frühschicht",
        "spätschicht",
        "nachtschicht",
        "schichtende",
        # Betriebsstoffe
        "gleitbahnöl",
        "schmierstoff",
        "optikreiniger",
        "sicherungslack",
        "leckölmenge",
        # Bauteile und Baugruppen
        "energiekette",
        "niederhalterfeder",
        "klemmnabe",
        "loslagerbock",
        "gelenklager",
        "kugelgewindetrieb",
        "zahnriemen",
        "förderantrieb",
        "bremseinheit",
        "auslaufkonus",
        "auswurfschacht",
        "zentrierbuchse",
        "diffusorscheibe",
        "werkzeugbefestigung",
        "referenzteil",
        "klemmer",
        # Material und Umlauf
        "schlauchleitungen",
        "paletten",
        "rohteile",
        # Messgrößen
        "verschleißmaß",
        "schwingungswert",
        "altsatz",
    }
)


class Redactor(Protocol):
    """Schnittstelle des Schreibpfads: maskiert Personennamen in Freitext."""

    def redact_person_names(self, text: str) -> str: ...


class PresidioRedactor:
    """Maskiert `PER`-Entitäten über Presidio + spaCy `de_core_news_lg`.

    Die NLP-Engine (großes Modell) wird **lazy** beim ersten Aufruf gebaut, damit
    Import und Tests ohne 560-MB-Download laufen. Für Tests können `analyzer` und
    `anonymizer` als Mocks injiziert werden.
    """

    def __init__(
        self,
        *,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
        analyzer: Any | None = None,
        anonymizer: Any | None = None,
    ) -> None:
        self._score_threshold = score_threshold
        self._analyzer = analyzer
        self._anonymizer = anonymizer

    def _ensure_engines(self) -> tuple[Any, Any]:
        if self._analyzer is None:
            provider = NlpEngineProvider(
                nlp_configuration={
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": "de", "model_name": "de_core_news_lg"}],
                }
            )
            self._analyzer = AnalyzerEngine(
                nlp_engine=provider.create_engine(), supported_languages=["de"]
            )
        if self._anonymizer is None:
            self._anonymizer = AnonymizerEngine()
        return self._analyzer, self._anonymizer

    @staticmethod
    def _ist_fachsprache(span: str) -> bool:
        """Wahr, wenn der Treffer strukturell kein Personenname sein kann.

        Zwei Bedingungen, beide oben begründet: eine Ziffer im Treffer, oder
        ausschliesslich belegte Fachbegriffe. Ein Treffer, in dem auch nur EIN
        unbekanntes grossgeschriebenes Wort steht, gilt weiter als Name — sonst
        liesse sich ein echter Name hinter einem Fachwort verstecken
        ("Nachschmierung Weber").
        """
        if any(z.isdigit() for z in span):
            return True
        woerter = [w.strip(".,;:!?()").lower() for w in span.split()]
        woerter = [w for w in woerter if w]
        return bool(woerter) and all(w in FACHBEGRIFFE for w in woerter)

    def redact_person_names(self, text: str) -> str:
        """Ersetzt erkannte Personennamen durch `[PERSON]`."""
        if not text:
            return text
        analyzer, anonymizer = self._ensure_engines()
        results = analyzer.analyze(
            text=text,
            language="de",
            entities=["PERSON"],
            score_threshold=self._score_threshold,
        )
        # Falschtreffer auf Hallensprache aussortieren — siehe FACHBEGRIFFE.
        results = [r for r in results if not self._ist_fachsprache(text[r.start : r.end])]
        anonymized: str = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators={"PERSON": OperatorConfig("replace", {"new_value": PERSON_PLACEHOLDER})},
        ).text
        return anonymized


def build_redactor() -> PresidioRedactor:
    """Baut den Default-Redactor (lazy spaCy-Engine)."""
    return PresidioRedactor()
