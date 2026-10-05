"""Train urgency candidates on synthetic data and persist the best.

Selects by recall on levels 1-2 first, then interpretability
(LogisticRegression > RandomForest > XGBoost). All outputs are synthetic-only.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import cohen_kappa_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from synthetic import FEATURE_COLUMNS, SyntheticConfig, generate

ARTIFACTS = Path(__file__).parent / "artifacts"
MODEL_VERSION = "synthetic-v0.1"
INTERPRETABILITY = {"logreg": 0, "rf": 1, "xgb": 2}


def build_candidates() -> dict[str, Pipeline]:
    logreg = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            (
                "clf",
                LogisticRegression(max_iter=2000, class_weight="balanced"),
            ),
        ]
    )
    rf = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=300,
                    class_weight="balanced_subsample",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    xgb = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            (
                "clf",
                XGBClassifier(
                    n_estimators=400,
                    max_depth=5,
                    learning_rate=0.06,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    objective="multi:softprob",
                    num_class=5,
                    eval_metric="mlogloss",
                    tree_method="hist",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    return {"logreg": logreg, "rf": rf, "xgb": xgb}


def recall_12(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = np.isin(y_true, [1, 2])
    if not mask.any():
        return 0.0
    return float(recall_score(y_true[mask], y_pred[mask], average="micro"))


def calibrate(estimator: Pipeline, x_train: pd.DataFrame, y_train: pd.Series) -> object:
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    calibrated = CalibratedClassifierCV(estimator=estimator, method="sigmoid", cv=cv)
    calibrated.fit(x_train, y_train)
    return calibrated


def metrics_for(
    name: str, model: object, x_test: pd.DataFrame, y_test: pd.Series
) -> dict[str, object]:
    proba = model.predict_proba(x_test)
    raw_pred = np.asarray(model.predict(x_test)).astype(int)
    classes = [int(c) for c in model.classes_]
    offset = 1 if min(classes) == 0 else 0
    pred = raw_pred + offset
    level_classes = [c + offset for c in classes]
    auc = float(
        roc_auc_score(
            pd.get_dummies(y_test).reindex(columns=level_classes, fill_value=0).values,
            proba,
            multi_class="ovr",
        )
    )
    recalls = {
        str(level): float(recall_score(y_test, pred, labels=[level], average="micro",
                                       zero_division=0))
        for level in [1, 2, 3, 4, 5]
    }
    within_one = float(np.mean(np.abs(y_test.values - pred.astype(int)) <= 1))
    return {
        "name": name,
        "auc_ovr": round(auc, 3),
        "recall_per_class": recalls,
        "recall_12": round(recall_12(y_test.values, pred.astype(int)), 3),
        "kappa": round(float(cohen_kappa_score(y_test, pred)), 3),
        "within_1_accuracy": round(within_one, 3),
    }


def main() -> None:
    frame = generate(SyntheticConfig(n=6000, seed=42))
    x = frame[FEATURE_COLUMNS]
    y = frame["level"].astype(int)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.25, stratify=y, random_state=42
    )
    medians = x_train.median(numeric_only=True).to_dict()
    results: dict[str, dict[str, object]] = {}
    fitted: dict[str, object] = {}
    for name, candidate in build_candidates().items():
        if name == "xgb":
            y_enc = (y_train - 1).astype(int)
            counts = y_train.value_counts(normalize=True).to_dict()
            sample_weight = y_train.map(lambda v, _c=counts: 1.0 / _c[int(v)]).values
            candidate.fit(x_train, y_enc, clf__sample_weight=sample_weight)
            fitted[name] = calibrate(candidate, x_train, y_enc)
        else:
            candidate.fit(x_train, y_train)
            fitted[name] = calibrate(candidate, x_train, y_train)
        results[name] = metrics_for(name, fitted[name], x_test, y_test)
    ranked = sorted(
        results.values(),
        key=lambda item: (-float(item["recall_12"]), INTERPRETABILITY[str(item["name"])]),
    )
    best_name = str(ranked[0]["name"])
    best_model = fitted[best_name]
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, ARTIFACTS / "model.joblib")
    joblib.dump(medians, ARTIFACTS / "medians.joblib")
    joblib.dump(FEATURE_COLUMNS, ARTIFACTS / "features.joblib")
    metadata = {
        "model_version": MODEL_VERSION,
        "selected_model": best_name,
        "synthetic_only": True,
        "seed": 42,
        "features": FEATURE_COLUMNS,
        "metrics": results,
        "selection": "recall on levels 1-2 first, then interpretability",
    }
    (ARTIFACTS / "metadata.json").write_text(json.dumps(metadata, indent=2),
                                             encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
