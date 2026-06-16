# ============================================================
#  FOREMAN — reasoners/failure/grounding.py
#  Zweck: Bau der GroundingSource-Liste fürs Gateway (F-REC, Baustein 2) aus der
#         Vorhersage + ihren SHAP-Top-Faktoren + den NEXUS-Recall-Treffern.
#  Architektur-Einordnung: Reasoning-Schicht (F-REC) → LLM-Schicht (F-LLM). Der
#         Reasoner LIEFERT die Quellen; das Gateway ERZWINGT Spotlighting/Grounding.
#  ZENTRALE SICHERHEITS-INVARIANTE:
#         - Vorhersage (`pred:<id>`) + SHAP-Faktoren (`factor:<name>`) sind
#           `trusted=True` — modell-autoritative, strukturierte Daten. Ihr Content
#           trägt die AUTORITATIVEN ZAHLEN (Wahrscheinlichkeit, Horizont, Messwert,
#           SHAP): nur was hier belegt ist, darf das LLM zitieren (Invariante I, der
#           numerische Post-Check im Service verwirft jede andere Zahl).
#         - NEXUS-Recall (`recall:<n>`) ist externer Substrat-Freitext → IMMER
#           `trusted=False` (Spotlighting-Quelle, nie Instruktion, belegt keine Zahl).
#  Konvention (§6): reine, netzfreie Funktionen.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from foreman.llm import GroundingSource
from foreman.reasoners.event_chain.recall import RecallItem
from foreman.reasoners.failure.schema import FailurePredictionRead, TopFactor

# Präfix der Recall-Quellen-IDs (untrusted, externer Vergangenheits-Freitext).
RECALL_SOURCE_PREFIX = "recall"


def _num(value: float) -> str:
    """Kompakte, kanonische FIXKOMMA-Darstellung (Grounding-Beleg + Lesbarkeit).

    Bewusst KEINE wissenschaftliche Notation: der Gateway-Post-Check (§13.3) zerlegt
    Zahlen mit `\\d+(?:[.,]\\d+)?` und kennt kein 'e'. '1e-05' würde sonst in '1'/'05'
    zerfallen — eine belegte Zahl würde fälschlich als unbelegt (oder die zerlegten
    Mantissen-Ziffern als belegt) gewertet. Fixkomma hält Quell- und Post-Check-
    Kanonisierung deckungsgleich (Invariante I).
    """
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _prediction_content(prediction: FailurePredictionRead) -> str:
    """Trusted-Content der Vorhersage-Quelle: die autoritativen Kennzahlen.

    Enthält bewusst auch die `machine_id` — sie ist strukturelle DB-Wahrheit und
    damit eine BELEGTE Zahl: nennt der Empfehlungstext die Maschinennummer, fällt sie
    nicht fälschlich durch den numerischen Post-Check (Invariante I, kein False-Reject).
    """
    return (
        f"Maschine {prediction.machine_id}: "
        f"Ausfallwahrscheinlichkeit {_num(prediction.probability)} "
        f"im Vorhersagehorizont von {prediction.horizon_h} Stunden; "
        f"operative Entscheidung {prediction.decision} "
        f"(kostensensitiver Schwellwert {_num(prediction.decision_threshold)})."
    )


def _factor_content(factor: TopFactor) -> str:
    """Trusted-Content einer SHAP-Faktor-Quelle (assoziativ, nicht kausal, §16.3)."""
    richtung = (
        "erhöht das Risikosignal"
        if factor.direction == "increases_risk"
        else "senkt das Risikosignal"
    )
    return (
        f"Faktor {factor.feature}: Messwert {_num(factor.value)}, "
        f"SHAP-Beitrag {_num(factor.shap)} ({richtung})."
    )


def build_recommendation_sources(
    prediction: FailurePredictionRead, recall_items: Sequence[RecallItem] = ()
) -> list[GroundingSource]:
    """Baut die Grounding-Quellen für die Werker-Empfehlung.

    Reihenfolge: Vorhersage (`pred:<id>`, trusted) → je SHAP-Top-Faktor
    (`factor:<name>`, trusted) → je Recall-Treffer (`recall:<n>`, untrusted).
    Das `trusted`-Flag wird NIE angehoben — Recall-Inhalte bleiben untrusted.
    """
    sources: list[GroundingSource] = [
        GroundingSource(
            source_id=f"pred:{prediction.id}",
            content=_prediction_content(prediction),
            trusted=True,
        )
    ]
    sources.extend(
        GroundingSource(
            source_id=f"factor:{factor.feature}",
            content=_factor_content(factor),
            trusted=True,
        )
        for factor in prediction.top_factors
    )
    sources.extend(
        GroundingSource(
            source_id=f"{RECALL_SOURCE_PREFIX}:{index}", content=item.content, trusted=False
        )
        for index, item in enumerate(recall_items)
    )
    return sources


def allowed_source_ids(sources: Sequence[GroundingSource]) -> tuple[str, ...]:
    """Die Whitelist gültiger source_ids (für den WorkerRecommendation-Output-Guard)."""
    return tuple(source.source_id for source in sources)
