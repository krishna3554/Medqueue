"""Deterministic top-3 explanations for the predicted urgency level."""

from typing import Any

from app.triage import model as triage_model


def _fallback_top3(row: dict[str, float], medians: dict[str, float]) -> list[dict]:
    scored = []
    for name, value in row.items():
        baseline = medians.get(name, 0.0)
        scale = abs(baseline) + 1.0
        scored.append((abs(value - baseline) / scale, name, value))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"name": name, "value": value, "contribution": round(float(score), 4)}
        for score, name, value in scored[:3]
    ]


def explain(
    symptoms: set[str], vitals: dict[str, Any], age: int | None, predicted_level: int
) -> dict[str, Any]:
    """Return top-3 features and a one-sentence rationale, deterministically."""
    triage_model._load()
    row = triage_model.feature_row(symptoms, vitals, age) or {}
    medians = dict(triage_model._medians or {})
    features = list(triage_model._features or list(row))
    contributions: list[dict] | None = None
    if triage_model._model is not None and row:
        try:
            import numpy as np
            import pandas as pd
            import shap

            estimator = triage_model._model
            base = estimator
            while hasattr(base, "estimator_"):
                base = base.estimator_
            while hasattr(base, "estimators_") and not hasattr(base, "tree_"):
                # CalibratedClassifierCV holds fitted pipelines per fold.
                candidate = base.estimators_[0]
                while hasattr(candidate, "steps"):
                    candidate = candidate.steps[-1][1]
                base = candidate
                break
            frame = pd.DataFrame([{column: row[column] for column in features}])
            explainer = shap.TreeExplainer(base)
            values = explainer.shap_values(frame)
            if isinstance(values, list):
                classes = [int(c) for c in triage_model._model.classes_]
                offset = 1 if classes and min(classes) == 0 else 0
                levels = [c + offset for c in classes]
                index = levels.index(predicted_level) if predicted_level in levels else 0
                shap_row = np.asarray(values[index])[0]
            else:
                shap_row = np.asarray(values)[0]
                if shap_row.ndim > 1:
                    shap_row = shap_row[:, 0]
            order = sorted(
                range(len(features)),
                key=lambda i: (-abs(float(shap_row[i])), features[i]),
            )
            contributions = [
                {
                    "name": features[i],
                    "value": row[features[i]],
                    "contribution": round(float(shap_row[i]), 4),
                }
                for i in order[:3]
            ]
        except Exception:
            contributions = None
    if contributions is None:
        contributions = _fallback_top3(row, medians)
    parts = []
    for item in contributions:
        value = item["value"]
        label = item["name"].removeprefix("sym_").replace("_", " ")
        parts.append(f"{label} {value}")
    rationale = f"Urgency raised by: {', '.join(parts)}" if parts else "No key drivers."
    return {"top_factors": contributions, "rationale": rationale}
