"""Lazy synthetic-model loader. Rules-first; missing model falls back cleanly."""

import json
from pathlib import Path
from typing import Any

MODEL_VERSION_FALLBACK = "unavailable"

_artifacts_dir = Path(__file__).parents[3] / "ml" / "artifacts"
_model: Any | None = None
_medians: dict[str, float] | None = None
_features: list[str] | None = None
_metadata: dict[str, Any] | None = None
_loaded = False


def artifacts_dir() -> Path:
    import os

    override = os.getenv("MEDQUEUE_MODEL_DIR")
    return Path(override) if override else _artifacts_dir


def _load() -> None:
    global _model, _medians, _features, _metadata, _loaded
    if _loaded:
        return
    _loaded = True
    try:
        import joblib

        base = artifacts_dir()
        _model = joblib.load(base / "model.joblib")
        _medians = dict(joblib.load(base / "medians.joblib"))
        _features = list(joblib.load(base / "features.joblib"))
        _metadata = json.loads((base / "metadata.json").read_text(encoding="utf-8"))
    except Exception:
        _model, _medians, _features, _metadata = None, None, None, None


def is_available() -> bool:
    _load()
    return _model is not None


def model_version() -> str:
    _load()
    if isinstance(_metadata, dict) and _metadata.get("model_version"):
        return str(_metadata["model_version"])
    return MODEL_VERSION_FALLBACK


def feature_row(
    symptoms: set[str], vitals: dict[str, Any], age: int | None
) -> dict[str, float] | None:
    """Build the model feature row, imputing with training medians."""
    _load()
    if _features is None or _medians is None:
        return None
    normalized = {str(item).strip().lower() for item in symptoms}
    row: dict[str, float] = {}
    for column in _features:
        if column.startswith("sym_"):
            row[column] = 1.0 if column[4:] in normalized else 0.0
        elif column == "age":
            row[column] = float(age) if age is not None else _medians.get(column, 30.0)
        elif column == "age_band":
            band = 2
            if age is not None:
                band = 0 if age < 2 else (1 if age < 18 else (2 if age < 65 else 3))
            row[column] = float(band)
        elif column == "sex":
            sex = vitals.get("sex", _medians.get(column, 0.5))
            row[column] = float(sex) if sex in (0, 1, 0.0, 1.0) else 0.5
        elif column in ("shock_index", "fever_flag", "hypoxia_flag"):
            pulse = vitals.get("pulse")
            sbp = vitals.get("sbp")
            temp = vitals.get("temp_c")
            spo2 = vitals.get("spo2")
            if column == "shock_index":
                row[column] = (
                    float(pulse) / float(sbp)
                    if isinstance(pulse, (int, float))
                    and isinstance(sbp, (int, float))
                    and sbp
                    else _medians.get(column, 0.67)
                )
            elif column == "fever_flag":
                row[column] = (
                    1.0 if isinstance(temp, (int, float)) and temp >= 38.0 else 0.0
                )
            else:
                row[column] = (
                    1.0 if isinstance(spo2, (int, float)) and spo2 < 94.0 else 0.0
                )
        elif column.endswith("_missing"):
            vital = column[: -len("_missing")]
            row[column] = 0.0 if isinstance(vitals.get(vital), (int, float)) else 1.0
        else:
            value = vitals.get(column)
            row[column] = (
                float(value)
                if isinstance(value, (int, float))
                else float(_medians.get(column, 0.0))
            )
    return row


def predict(
    symptoms: set[str], vitals: dict[str, Any], age: int | None
) -> dict[str, Any] | None:
    """Return level/probabilities/version, or None when AI is unavailable."""
    _load()
    if _model is None or _features is None:
        return None
    try:
        import pandas as pd

        row = feature_row(symptoms, vitals, age)
        if row is None:
            return None
        frame = pd.DataFrame([{column: row[column] for column in _features}])
        proba = [float(value) for value in _model.predict_proba(frame)[0]]
        classes = [int(item) for item in _model.classes_]
        offset = 1 if classes and min(classes) == 0 else 0
        levels = [item + offset for item in classes]
        best = int(levels[int(max(range(len(proba)), key=lambda i: proba[i]))])
        probabilities = {str(level): proba[i] for i, level in enumerate(levels)}
        return {
            "level": best,
            "probabilities": probabilities,
            "model_version": model_version(),
            "features": row,
        }
    except Exception:
        return None


def reset_cache() -> None:
    """Test-only helper to force artifact reload."""
    global _model, _medians, _features, _metadata, _loaded
    _model, _medians, _features, _metadata, _loaded = None, None, None, None, False
