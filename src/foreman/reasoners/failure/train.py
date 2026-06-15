# ============================================================
#  FOREMAN — reasoners/failure/train.py
#  Zweck: Offline-Training des Ausfallvorhersage-Reasoners (F-PRED) als
#         reproduzierbarer CLI-Schritt. LightGBM-Binärklassifikation
#         (Ausfallwahrscheinlichkeit), kostensensitiver Schwellwert auf der
#         PR-Kurve, Eval auf dem LAUF-DISJUNKTEN Split mit klassenungleichgewicht-
#         tauglichen Metriken (PR-AUC/ROC-AUC/Brier). Speichert Booster + Metadaten.
#  Architektur-Einordnung: Reasoning-Schicht (F-PRED), Offline-Trainingspfad.
#         FOREMAN trainiert NICHT zur Laufzeit (§10.4) — dies ist ein
#         Vordergrund-CLI-Schritt, kein Job-Worker.
#  Aufruf:
#    python -m foreman.reasoners.failure.train \
#        --scenarios bearing_drift,tool_wear,lubrication_correlation,healthy_baseline \
#        --seeds 1,2,3,4 --holdout-seeds 4 --horizon-days 14 --out <artefakt>
#
#  EHRLICHKEIT (§16): Die Eval-Metriken sind FUNKTIONSNACHWEIS (die Pipeline
#         rechnet korrekt), KEIN Realitätsnachweis. Auf Simulationsdaten misst die
#         Eval, wie gut das Modell den Simulator zurücklernt — nicht reale
#         Ausfälle. So benannt im Trainings-Log (train_summary), im Code-Header
#         und in der Model Card. validation_status=simulation_only ist gesetzt.
# ============================================================
from __future__ import annotations

import argparse
import hashlib
import sys
import warnings
from collections.abc import Sequence
from datetime import timedelta

import lightgbm as lgb
import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
)

from foreman.adapters.simulation.scenario import Scenario, load_scenario_by_name
from foreman.logging_setup import INFO, OK, get_logger
from foreman.reasoners.failure.dataset import (
    DEFAULT_STEP,
    TrainingDataset,
    build_dataset,
    load_runs,
    split_by_seed,
)
from foreman.reasoners.failure.model import ModelMetadata, save_artifact

logger = get_logger("foreman.reasoners.failure.train")

# Kostensensitiver Default: Schwellwert bei mindestens diesem Recall mit max. Precision.
DEFAULT_TARGET_RECALL = 0.80
DEFAULT_MODEL_VERSION = "lgbm-failure-2026.06"


def scenario_hash(scenario: Scenario) -> str:
    """Stabiler Inhalts-Hash eines Szenarios (Provenienz im Artefakt)."""
    payload = scenario.model_dump_json().encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def compute_metrics(y_true: Sequence[int], proba: Sequence[float]) -> dict[str, float]:
    """Klassenungleichgewicht-taugliche Eval-Metriken (Funktionsnachweis, §16).

    PR-AUC (Average Precision) primär, dazu ROC-AUC und Brier. Bei einklassigem
    Eval-Satz sind PR-/ROC-AUC undefiniert → NaN (ehrlich, nicht geschönt).
    """
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(proba, dtype=float)
    both_classes = 0 < int(y.sum()) < len(y)
    return {
        "pr_auc": float(average_precision_score(y, p)) if both_classes else float("nan"),
        "roc_auc": float(roc_auc_score(y, p)) if both_classes else float("nan"),
        "brier": float(brier_score_loss(y, p)),
    }


def choose_threshold(y_true: Sequence[int], proba: Sequence[float], target_recall: float) -> float:
    """Wählt den Schwellwert auf der PR-Kurve: min. `target_recall`, max. Precision.

    Fällt auf 0.5 zurück, wenn kein Schwellwert den Ziel-Recall erreicht oder der
    Eval-Satz einklassig ist (kein kostensensitiver Punkt ableitbar).
    """
    y = np.asarray(y_true, dtype=int)
    if not 0 < int(y.sum()) < len(y):
        return 0.5
    precision, recall, thresholds = precision_recall_curve(y, np.asarray(proba, dtype=float))
    best_threshold = 0.5
    best_precision = -1.0
    for prec, rec, thr in zip(precision[:-1], recall[:-1], thresholds, strict=True):
        if rec >= target_recall and prec > best_precision:
            best_precision = float(prec)
            best_threshold = float(thr)
    return best_threshold


def train_and_evaluate(
    train_ds: TrainingDataset,
    eval_ds: TrainingDataset,
    *,
    seed: int,
    model_version: str,
    scenario_hashes: dict[str, str],
    target_recall: float = DEFAULT_TARGET_RECALL,
) -> tuple[lgb.Booster, ModelMetadata]:
    """Trainiert LightGBM auf dem Train-Satz, evaluiert auf dem (lauf-disjunkten)
    Eval-Satz und baut Booster + Metadaten (reproduzierbar über `seed`)."""
    x_train, y_train, _ = train_ds.matrix()
    x_eval, y_eval, _ = eval_ds.matrix()
    # Eval mit beiden Klassen ist Pflicht: PR-/ROC-AUC sind sonst undefiniert (NaN) und
    # das Artefakt würde mit NaN-Metriken speichern und nicht mehr laden. Lieber laut
    # scheitern als ein kaputtes Artefakt erzeugen — der Holdout ist falsch gewählt.
    if len(set(y_eval)) < 2:
        raise ValueError(
            "❌ Eval-Split ist einklassig (oder leer) — keine aussagekräftige PR-/ROC-AUC "
            "ableitbar. Wähle einen Holdout mit positiven UND negativen Läufen "
            "(z. B. ein Failure- plus ein Healthy-Szenario im selben Holdout-Seed)."
        )
    n_neg, n_pos = train_ds.class_balance()
    # Imbalance: Class-Weights (scale_pos_weight = #negativ/#positiv), KEIN SMOTE (§4-Research).
    scale_pos_weight = (n_neg / n_pos) if n_pos else 1.0

    classifier = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=5,
        scale_pos_weight=scale_pos_weight,
        random_state=seed,
        n_jobs=1,
        deterministic=True,
        force_col_wise=True,
        verbose=-1,
    )
    with warnings.catch_warnings():
        # Wir nutzen positionsbasierte Spalten (Feature-Schema ist im Artefakt fixiert);
        # die sklearn-Warnung zu fehlenden Feature-Namen ist hier redundant.
        warnings.filterwarnings("ignore", message=".*does not have valid feature names.*")
        classifier.fit(np.asarray(x_train, dtype=float), np.asarray(y_train, dtype=int))
        proba_eval = classifier.predict_proba(np.asarray(x_eval, dtype=float))[:, 1]
    metrics = compute_metrics(y_eval, proba_eval)
    threshold = choose_threshold(y_eval, proba_eval, target_recall)

    metadata = ModelMetadata(
        model_version=model_version,
        training_source="simulation",
        data_regime="simulation",
        validation_status="simulation_only",
        horizon_h=round(train_ds.horizon.total_seconds() / 3600.0),
        lookback_h=round(train_ds.lookback.total_seconds() / 3600.0),
        decision_threshold=threshold,
        feature_schema=train_ds.feature_names,
        scenario_hashes=scenario_hashes,
        seed=seed,
        metrics=metrics,
        n_train=len(x_train),
        n_eval=len(x_eval),
        n_pos_train=n_pos,
        n_neg_train=n_neg,
    )
    booster: lgb.Booster = classifier.booster_
    return booster, metadata


def train_summary(metadata: ModelMetadata) -> str:
    """Trainings-Log mit Ehrlichkeits-Banner — Metriken NIE als »Genauigkeit der
    Ausfallvorhersage« verkauft (§16)."""
    return (
        f"📚 F-PRED Trainingsartefakt '{metadata.model_version}'\n"
        f"   data_regime={metadata.data_regime}  validation_status={metadata.validation_status}\n"
        f"   Horizont={metadata.horizon_h}h  Schwellwert={metadata.decision_threshold:.3f}  "
        f"Seed={metadata.seed}\n"
        f"   Train: {metadata.n_train} Samples ({metadata.n_pos_train} positiv / "
        f"{metadata.n_neg_train} negativ)   Eval: {metadata.n_eval} Samples\n"
        f"   Eval-Metriken: PR-AUC={metadata.metrics['pr_auc']:.3f}  "
        f"ROC-AUC={metadata.metrics['roc_auc']:.3f}  Brier={metadata.metrics['brier']:.3f}\n"
        f"   ⚠️  Diese Eval-Metriken sind Funktionsnachweis (die Pipeline rechnet korrekt), "
        f"KEIN Realitätsnachweis. Auf Simulationsdaten misst die Eval, wie gut das Modell den "
        f"Simulator zurücklernt — nicht, wie gut es reale Ausfälle vorhersagt. Erst reale "
        f"Run-to-failure-Daten machen das Modell validierbar (validation_status="
        f"simulation_only; siehe docs/models/failure_prediction_model_card.md)."
    )


def run_training(
    *,
    scenario_names: Sequence[str],
    seeds: Sequence[int],
    holdout_seeds: set[int],
    horizon: timedelta,
    lookback: timedelta,
    step: timedelta,
    seed: int,
    model_version: str,
    out: str,
) -> ModelMetadata:
    """Orchestriert Daten-Bau → Split → Training → Eval → Artefakt speichern."""
    runs = load_runs(scenario_names, seeds)
    scenario_hashes = {name: scenario_hash(load_scenario_by_name(name)) for name in scenario_names}
    dataset = build_dataset(runs, horizon=horizon, lookback=lookback, step=step)
    train_ds, eval_ds = split_by_seed(dataset, holdout_seeds=holdout_seeds)
    booster, metadata = train_and_evaluate(
        train_ds, eval_ds, seed=seed, model_version=model_version, scenario_hashes=scenario_hashes
    )
    saved = save_artifact(out, booster, metadata)
    logger.info("%s F-PRED-Artefakt gespeichert: %s", OK, saved)
    print(train_summary(metadata))
    print(f"✅ Artefakt gespeichert: {saved}")
    return metadata


def _parse_int_set(raw: str) -> set[int]:
    return {int(token) for token in raw.split(",") if token.strip()}


def _parse_int_list(raw: str) -> list[int]:
    return [int(token) for token in raw.split(",") if token.strip()]


def _parse_names(raw: str) -> list[str]:
    return [token.strip() for token in raw.split(",") if token.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    """CLI-Einstieg des Offline-Trainings."""
    # Windows-Konsole (cp1252) auf UTF-8 stellen, damit die Emoji-Ausgabe nicht bricht.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="python -m foreman.reasoners.failure.train",
        description=(
            "Offline-Training des Ausfallvorhersage-Reasoners (F-PRED). "
            "Methoden-Demonstrator auf Simulationsdaten — validation_status=simulation_only."
        ),
    )
    parser.add_argument(
        "--scenarios",
        required=True,
        help="Komma-Liste der Szenario-Namen (mit ground_truth.failure)",
    )
    parser.add_argument(
        "--seeds", default="1,2,3,4", help="Komma-Liste der Seeds (Läufe je Szenario)"
    )
    parser.add_argument("--holdout-seeds", default="4", help="Seeds, die den Eval-Satz bilden")
    parser.add_argument(
        "--horizon-days", type=float, default=14.0, help="Vorhersagehorizont in Tagen"
    )
    parser.add_argument(
        "--lookback-hours", type=int, default=72, help="Vorlauf-Fenster der Features"
    )
    parser.add_argument(
        "--step-hours",
        type=int,
        default=int(DEFAULT_STEP.total_seconds() // 3600),
        help="Abtast-Schritt der Bezugszeitpunkte",
    )
    parser.add_argument("--seed", type=int, default=42, help="Trainings-Seed (Reproduzierbarkeit)")
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    parser.add_argument("--out", required=True, help="Zielverzeichnis des Artefakts")
    args = parser.parse_args(argv)

    logger.info("%s F-PRED-Training startet (Szenarien=%s)", INFO, args.scenarios)
    run_training(
        scenario_names=_parse_names(args.scenarios),
        seeds=_parse_int_list(args.seeds),
        holdout_seeds=_parse_int_set(args.holdout_seeds),
        horizon=timedelta(days=args.horizon_days),
        lookback=timedelta(hours=args.lookback_hours),
        step=timedelta(hours=args.step_hours),
        seed=args.seed,
        model_version=args.model_version,
        out=args.out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
