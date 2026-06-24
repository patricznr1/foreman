# ============================================================
#  FOREMAN — tests/reasoners/failure/test_prompts.py
#  Zweck: Regressionsschutz für den F-REC-System-Prompt. Der numerische Grounding-
#         Post-Check (§13.3) verlangt EXAKTE Übereinstimmung mit den Quellzahlen;
#         ein echtes Modell (claude-sonnet-4-5) rundet die hochpräzisen Quellwerte
#         (451.328363 → „451,3") oder rechnet um (336 h → „14 Tage") und fällt damit
#         fail-closed durch (422 — Empfehlung praktisch immer abgelehnt). Der Prompt
#         MUSS deshalb GAR KEINE Ziffern verlangen (rein qualitativ). Dieser Test
#         verhindert das versehentliche Zurückdrehen auf eine zahlen-erlaubende Regel.
#  Architektur-Einordnung: Quality Gate §10.3 (Unit, reine Strings).
# ============================================================
from __future__ import annotations

from foreman.reasoners.failure.prompts import (
    RECOMMENDATION_SYSTEM_PROMPT,
    build_recommendation_user_prompt,
)
from foreman.reasoners.failure.schema import FailurePredictionRead, TopFactor


def test_system_prompt_verlangt_zahlenfreie_qualitative_empfehlung() -> None:
    prompt = RECOMMENDATION_SYSTEM_PROMPT.lower()
    # Kernregel des Fixes: keine Ziffern, rein qualitativ, nichts runden/umrechnen.
    assert "keine ziffern" in prompt or "keine zahlen" in prompt
    assert "qualitativ" in prompt
    assert "runde nichts" in prompt
    # Die alte, den Bug auslösende Formulierung darf NICHT zurückkehren.
    assert "nur exakt so, wie sie in den quellen stehen" not in prompt


def test_user_prompt_traegt_zitier_anker_ohne_inline_zahlen() -> None:
    prediction = FailurePredictionRead(
        id=12,
        machine_id=7,
        reference_time="2026-06-24T15:07:00Z",
        horizon_h=336,
        probability=0.9998,
        decision_threshold=0.997,
        decision="elevated_risk",
        top_factors=[
            TopFactor(
                feature="maint__hours_since_last",
                value=451.328363,
                shap=4.970699,
                direction="increases_risk",
            )
        ],
        validation_status="simulation_only",
        data_regime="simulation",
        model_version="lgbm-failure-2026.06",
        created_at="2026-06-24T15:07:44Z",
    )
    user = build_recommendation_user_prompt(prediction)
    # Zitier-Anker vorhanden ...
    assert "[pred:12]" in user
    assert "[factor:maint__hours_since_last]" in user
    # ... aber die hochpräzisen Messwerte werden NICHT inline in den User-Prompt
    # dupliziert (sie kommen gespotlightet über die Grounding-Quellen).
    assert "451.328363" not in user
    assert "4.970699" not in user
