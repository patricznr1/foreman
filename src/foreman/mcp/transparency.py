# ============================================================
#  FOREMAN — mcp/transparency.py
#  Zweck: AI-Act-Transparenz-Wrapper (Art. 50(2), §10.5 Maßnahme 2). EIN
#         gemeinsamer Mechanismus, der jeden KI-stämmigen MCP-Output mit den
#         maschinenlesbaren Flags umhüllt — und Nicht-KI-Daten EHRLICH nicht als
#         KI kennzeichnet.
#  Architektur-Einordnung: MCP-Schicht (F7). Reine, testbare Datenklasse +
#         Builder; keine DB, kein Reasoner-Import.
#  Invariante II (Brief §2): KI-Output → ai_generated/generated_by/
#         requires_human_review/model_version; Vorhersage/Empfehlung zusätzlich
#         validation_status/data_regime (+ deterministischer validation_caveat).
#         Nicht-KI-Output → keine KI-Felder. Die Ehrlichkeit ist STRUKTURELL
#         erzwungen (Validator): ein unehrlicher Umschlag lässt sich nicht bauen.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, model_validator

# Der mandatierte Erzeuger-Marker (§10.5 Maßnahme 2). Nach außen sichtbar, aber
# bewusst neutral — kein internes Vokabular (Invariante III).
GENERATED_BY: Final = "foreman-ai"


class AiTransparency(BaseModel):
    """Der gemeinsame AI-Act-Transparenz-Umschlag jedes MCP-Outputs (Art. 50(2)).

    Wird als gemeinsames Feld in JEDES Tool-Ausgabeschema eingebettet. Die Flags
    sind EHRLICH, nicht pauschal: für KI-Output gesetzt, für rohe Daten leer. Der
    Validator macht die Ehrlichkeit strukturell — ein Nicht-KI-Umschlag kann keine
    KI-Metadaten tragen, ein KI-Umschlag keinen falschen Erzeuger.
    """

    # protected_namespaces=(): `model_version` ist ein Brief-mandatiertes Feld —
    # Pydantics `model_`-Namespace-Schutz wird hier bewusst aufgehoben.
    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    ai_generated: bool
    # Erzeuger-Marker — nur bei KI-Output gesetzt (= GENERATED_BY).
    generated_by: str | None = None
    # Menschliche Letztkontrolle nötig — nur bei KI-Output True (Art. 50(2)).
    requires_human_review: bool = False
    # Modell-/Artefakt-Version. Bei Reasonern ohne persistierte Version null (ehrlich).
    model_version: str | None = None
    # --- Sim-Vorbehalt (nur Vorhersage/Empfehlung) ---
    validation_status: str | None = None
    data_regime: str | None = None
    validation_caveat: str | None = None

    @model_validator(mode="after")
    def _enforce_honesty(self) -> AiTransparency:
        """Erzwingt die ehrliche Kennzeichnung pro Output-Typ (Invariante II)."""
        if self.ai_generated:
            # KI-Output: Erzeuger-Marker + Review-Pflicht sind nicht verhandelbar.
            if self.generated_by != GENERATED_BY:
                raise ValueError(
                    f"❌ KI-Output muss generated_by='{GENERATED_BY}' tragen "
                    f"(erhalten: {self.generated_by!r})."
                )
            if not self.requires_human_review:
                raise ValueError(
                    "❌ KI-Output muss requires_human_review=True tragen (Art. 50(2))."
                )
            return self
        # Nicht-KI-Output: kein einziges KI-Metadatum darf gesetzt sein (Ehrlichkeit).
        smuggled = (
            self.generated_by is not None
            or self.requires_human_review
            or self.model_version is not None
            or self.validation_status is not None
            or self.data_regime is not None
            or self.validation_caveat is not None
        )
        if smuggled:
            raise ValueError(
                "❌ Nicht-KI-Output darf keine KI-Metadaten tragen "
                "(keine pauschale Kennzeichnung — die Flags sind ehrlich)."
            )
        return self


def ai_transparency(
    *,
    model_version: str | None,
    validation_status: str | None = None,
    data_regime: str | None = None,
    validation_caveat: str | None = None,
) -> AiTransparency:
    """Baut den Transparenz-Umschlag für einen KI-stämmigen Output (Art. 50(2)).

    `model_version` ist Pflicht-Argument, darf aber null sein, wenn der erzeugende
    Reasoner keine Modell-Version persistiert (z. B. Ereignisketten) — das ist die
    ehrliche Darstellung, kein erfundener Wert. `validation_status`/`data_regime`/
    `validation_caveat` werden nur bei Vorhersage/Empfehlung mitgegeben.
    """
    return AiTransparency(
        ai_generated=True,
        generated_by=GENERATED_BY,
        requires_human_review=True,
        model_version=model_version,
        validation_status=validation_status,
        data_regime=data_regime,
        validation_caveat=validation_caveat,
    )


def non_ai_transparency() -> AiTransparency:
    """Baut den Transparenz-Umschlag für rohe/aggregierte Nicht-KI-Daten.

    Stammdaten, Sensortrends und Alarme sind keine KI-Outputs — sie werden EHRLICH
    nicht als KI gekennzeichnet (ai_generated=False, keine KI-Metadaten).
    """
    return AiTransparency(ai_generated=False)
