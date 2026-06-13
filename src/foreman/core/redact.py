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
        anonymized: str = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators={
                "PERSON": OperatorConfig("replace", {"new_value": PERSON_PLACEHOLDER})
            },
        ).text
        return anonymized


def build_redactor() -> PresidioRedactor:
    """Baut den Default-Redactor (lazy spaCy-Engine)."""
    return PresidioRedactor()
