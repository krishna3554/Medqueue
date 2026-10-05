"""Evaluate the persisted synthetic model on a fresh seed.

Writes metrics JSON plus a short markdown summary under docs/results/.
All numbers are synthetic-only and carry no clinical validity.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import cohen_kappa_score, recall_score, roc_auc_score

from synthetic import FEATURE_COLUMNS, SyntheticConfig, generate

ROOT = Path(__file__).parent
ARTIFACTS = ROOT / "artifacts"
RESULTS = ROOT.parent / "docs" / "results"


def subgroup_recall(y_true: pd.Series, y_pred: np.ndarray, ages: pd.Series) -> dict:
    bands = {"infant_<2": ages < 2, "child_2_17": (ages >= 2) & (ages < 18),
             "adult_18_64": (ages >= 18) & (ages < 65), "older_65+": ages >= 65}
    out = {}
    for name, mask in bands.items():
        if mask.sum() == 0:
            out[name] = {"n": 0, "recall_micro": 0.0}
        else:
            out[name] = {
                "n": int(mask.sum()),
                "recall_micro": round(
                    float(recall_score(y_true[mask], y_pred[mask], average="micro",
                                       zero_division=0)), 3),
            }
    return out


def main() -> None:
    model = joblib.load(ARTIFACTS / "model.joblib")
    metadata = json.loads((ARTIFACTS / "metadata.json").read_text(encoding="utf-8"))
    frame = generate(SyntheticConfig(n=3000, seed=123))
    x = frame[FEATURE_COLUMNS]
    y = frame["level"].astype(int)
    proba = model.predict_proba(x)
    raw_pred = np.asarray(model.predict(x)).astype(int)
    classes = [int(c) for c in model.classes_]
    offset = 1 if min(classes) == 0 else 0
    pred = raw_pred + offset
    y_enc = (y - offset).astype(int) if offset else y
    y_bin = pd.get_dummies(y_enc).reindex(columns=classes, fill_value=0).values
    report = {
        "model_version": metadata["model_version"],
        "synthetic_only": True,
        "n": len(frame),
        "auc_ovr": round(float(roc_auc_score(y_bin, proba, multi_class="ovr")), 3),
        "recall_per_class": {
            str(level): round(float(recall_score(y, pred, labels=[level],
                                                 average="micro", zero_division=0)), 3)
            for level in [1, 2, 3, 4, 5]
        },
        "recall_12": round(float(recall_score(y[np.isin(y, [1, 2])],
                                              pred[np.isin(y, [1, 2])],
                                              average="micro", zero_division=0)), 3),
        "kappa": round(float(cohen_kappa_score(y, pred)), 3),
        "within_1_accuracy": round(float(np.mean(np.abs(y.values - pred) <= 1)), 3),
        "subgroup_by_age_band": subgroup_recall(y, pred, frame["age"]),
    }
    prob_urgent = proba[:, [classes.index(1 - offset), classes.index(2 - offset)]].sum(
        axis=1
    )
    urgent_true = y.isin([1, 2]).astype(int).values
    prob_true, prob_pred = calibration_curve(urgent_true, prob_urgent, n_bins=10,
                                             strategy="uniform")
    report["calibration_curve"] = {
        "prob_true": [round(float(v), 3) for v in prob_true],
        "prob_pred": [round(float(v), 3) for v in prob_pred],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "model_evaluation.json").write_text(json.dumps(report, indent=2),
                                                   encoding="utf-8")
    lines = [
        "# Model evaluation (synthetic-only, draft)",
        "",
        "Status: draft, pending clinical review. Decision support only.",
        "All rows are synthetic from `ml/synthetic.py` (seed 123); no clinical validity.",
        "",
        f"Model: `{report['model_version']}` n={report['n']}",
        f"AUC (ovr): {report['auc_ovr']}",
        f"Recall L1-2: {report['recall_12']} "
        f"(L1 {report['recall_per_class']['1']}, L2 {report['recall_per_class']['2']})",
        f"Cohen kappa: {report['kappa']}",
        f"Within ±1 accuracy: {report['within_1_accuracy']}",
        "",
        "## Subgroup recall by age band",
        "",
    ]
    for name, stats in report["subgroup_by_age_band"].items():
        lines.append(f"- {name}: n={stats['n']} recall={stats['recall_micro']}")
    (RESULTS / "model_evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
