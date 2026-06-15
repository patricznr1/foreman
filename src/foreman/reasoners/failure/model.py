# ============================================================
#  FOREMAN — reasoners/failure/model.py
#  Zweck: Inferenz-Schicht des Ausfallvorhersage-Reasoners (F-PRED). Lädt das
#         Offline-Trainingsartefakt (LightGBM-Booster + Metadaten), liefert die
#         Ausfallwahrscheinlichkeit (`predict`) und die SHAP-Faktor-Attribution
#         (welche Features die Vorhersage trieben). FOREMAN trainiert NICHT zur
#         Laufzeit (§10.4) — diese Schicht lädt nur.
#  Architektur-Einordnung: Reasoning-Schicht (F-PRED). Das Artefakt ist ein
#         Verzeichnis: `model.txt` (LightGBM) + `metadata.json` (Provenienz).
#  Sicherheit (§13.3): Die Zahlen (Wahrscheinlichkeit, SHAP-Werte) sind
#         autoritativ vom Modell — sie kommen NIE aus einem LLM.
#  STRUKTURELLE EHRLICHKEIT (§16): `validation_status`/`data_regime`/
#         `model_version` stammen aus den Artefakt-Metadaten und werden in jede
#         FailurePrediction durchgereicht — der Sim-Vorbehalt ist nicht abstreifbar.
# ============================================================
from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import Literal

import lightgbm as lgb
import numpy as np
import shap
from pydantic import BaseModel, ConfigDict, Field

from foreman.reasoners.failure.features import to_vector
from foreman.reasoners.failure.schema import FactorDirection, TopFactor

# Dateinamen im Artefakt-Verzeichnis.
MODEL_FILE = "model.txt"
METADATA_FILE = "metadata.json"
# Standardanzahl erklärender SHAP-Top-Faktoren.
DEFAULT_TOP_K = 6
# Gebündeltes Demonstrator-Artefakt (auf Simulationsdaten trainiert, §16) — der
# Service lädt es per Default; per Override (FOREMAN_FAILURE_MODEL_PATH) ersetzbar.
DEFAULT_ARTIFACT_PATH = Path(__file__).parent / "artifacts" / "failure_lgbm"


class ModelMetadata(BaseModel):
    """Provenienz + Vertrag des Trainingsartefakts (mit dem Modell persistiert).

    `training_source`/`data_regime`/`validation_status` sind hart auf die
    Simulation festgelegt (§16) — kommen je echte Daten, ändert sich allein das
    Trainingsset, nicht die Schnittstelle. `feature_schema` fixiert die
    Spaltenreihenfolge (Konsistenz Training↔Inferenz). Die Eval-`metrics` sind
    Funktionsnachweis, KEIN Realitätsnachweis (Model Card §„Verifikation ≠
    Validierung").
    """

    # protected_namespaces=(): `model_version` ist ein Brief-mandatiertes Feld.
    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_version: str = Field(min_length=1)
    training_source: Literal["simulation"]
    data_regime: Literal["simulation"]
    validation_status: Literal["simulation_only"]
    horizon_h: int = Field(gt=0)
    # Vorlauf-Fenster der Features (Stunden) — muss bei der Inferenz exakt dem
    # Training entsprechen (Feature-Verteilungs-Konsistenz). Default = Trainings-Default.
    lookback_h: int = Field(default=72, gt=0)
    decision_threshold: float = Field(ge=0.0, le=1.0)
    feature_schema: tuple[str, ...] = Field(min_length=1)
    scenario_hashes: dict[str, str]
    seed: int
    metrics: dict[str, float]
    n_train: int = Field(ge=0)
    n_eval: int = Field(ge=0)
    n_pos_train: int = Field(ge=0)
    n_neg_train: int = Field(ge=0)


def save_artifact(path: str | Path, booster: lgb.Booster, metadata: ModelMetadata) -> Path:
    """Speichert Booster + Metadaten als Artefakt-Verzeichnis. Liefert den Pfad."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(directory / MODEL_FILE))
    (directory / METADATA_FILE).write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
    return directory


class FailureModel:
    """Geladenes Artefakt: Booster + Metadaten + SHAP-TreeExplainer (Inferenz)."""

    def __init__(
        self, booster: lgb.Booster, metadata: ModelMetadata, *, top_k: int = DEFAULT_TOP_K
    ) -> None:
        self._booster = booster
        self._metadata = metadata
        self._top_k = top_k
        # TreeExplainer ist deterministisch gegeben das Modell (exakte SHAP-Werte).
        self._explainer = shap.TreeExplainer(booster)

    @property
    def metadata(self) -> ModelMetadata:
        return self._metadata

    @property
    def feature_schema(self) -> tuple[str, ...]:
        return self._metadata.feature_schema

    @property
    def decision_threshold(self) -> float:
        return self._metadata.decision_threshold

    @property
    def horizon_h(self) -> int:
        return self._metadata.horizon_h

    def _shap_row(self, matrix: np.ndarray) -> np.ndarray:
        """Extrahiert die SHAP-Werte der Positiv-Klasse für die eine Zeile (defensiv)."""
        with warnings.catch_warnings():
            # Bekannte shap-Formatumstellung (binäres LightGBM → Liste je Klasse):
            # wir behandeln beide Formen unten explizit, die Warnung ist redundant.
            warnings.filterwarnings(
                "ignore",
                message=".*TreeExplainer shap values output has changed.*",
                category=UserWarning,
            )
            values = self._explainer.shap_values(matrix)
        if isinstance(values, list):  # ältere shap-Form: Liste je Klasse
            values = values[1] if len(values) > 1 else values[0]
        array = np.asarray(values, dtype=float)
        if array.ndim == 3:  # (n, features, classes) → letzte Klasse
            array = array[..., -1]
        row: np.ndarray = array[0]
        return row

    def predict(self, features: dict[str, float]) -> tuple[float, list[TopFactor]]:
        """Liefert Ausfallwahrscheinlichkeit + SHAP-Top-Faktoren für einen Feature-Dict.

        Fehlende Features werden zu NaN (LightGBM-konform) und tauchen NICHT als
        Top-Faktor auf — erklärt wird ausschließlich mit tatsächlich vorhandenen
        Signalen.
        """
        vector = to_vector(features, self._metadata.feature_schema)
        matrix = np.array([vector], dtype=float)
        proba = float(self._booster.predict(matrix)[0])
        proba = min(max(proba, 0.0), 1.0)  # numerische Sicherheit

        shap_row = self._shap_row(matrix)
        candidates: list[tuple[str, float, float]] = [
            (name, value, float(shap_value))
            for name, value, shap_value in zip(
                self._metadata.feature_schema, vector, shap_row, strict=True
            )
            if math.isfinite(value)
        ]
        candidates.sort(key=lambda item: abs(item[2]), reverse=True)
        factors = [
            TopFactor(
                feature=name,
                value=value,
                shap=shap_value,
                direction=_direction(shap_value),
            )
            for name, value, shap_value in candidates[: self._top_k]
        ]
        return proba, factors


def _direction(shap_value: float) -> FactorDirection:
    """SHAP-Vorzeichen → Wirkrichtung (assoziativ, nicht kausal — Model Card)."""
    return "increases_risk" if shap_value >= 0.0 else "decreases_risk"


def load_metadata(path: str | Path) -> ModelMetadata:
    """Lädt nur die Metadaten eines Artefakts (ohne Booster/SHAP)."""
    directory = Path(path)
    return ModelMetadata.model_validate_json(
        (directory / METADATA_FILE).read_text(encoding="utf-8")
    )


def load_model(path: str | Path, *, top_k: int = DEFAULT_TOP_K) -> FailureModel:
    """Lädt ein Artefakt-Verzeichnis (Booster + Metadaten) als FailureModel."""
    directory = Path(path)
    booster = lgb.Booster(model_file=str(directory / MODEL_FILE))
    metadata = load_metadata(directory)
    return FailureModel(booster, metadata, top_k=top_k)
