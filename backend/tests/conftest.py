"""Shared fixtures: hermetic tiny triage model for tests.

ml/artifacts/*.joblib are gitignored, so fresh checkouts have no model
binaries. Every test therefore gets MEDQUEUE_MODEL_DIR pointed at a tiny
synthetic model trained once per session, keeping the suite deterministic
with or without repo artifacts.
"""

import json
import os
import sys
from pathlib import Path

import pytest

from app.triage import model as triage_model

TINY_VERSION = "test-tiny-v0"


def _repo_root() -> Path:
    return Path(__file__).parents[2]


def _build_tiny_model(target: Path) -> None:
    ml_dir = str(_repo_root() / "ml")
    sys.path.insert(0, ml_dir)
    try:
        import joblib
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from synthetic import FEATURE_COLUMNS, SyntheticConfig, generate

        frame = generate(SyntheticConfig(n=500, seed=7))
        features = frame[FEATURE_COLUMNS]
        labels = frame["level"].astype(int)
        medians = features.median(numeric_only=True).to_dict()
        clf: Pipeline = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                (
                    "clf",
                    RandomForestClassifier(n_estimators=25, random_state=7, n_jobs=1),
                ),
            ]
        )
        clf.fit(features, labels)
        target.mkdir(parents=True, exist_ok=True)
        joblib.dump(clf, target / "model.joblib")
        joblib.dump(medians, target / "medians.joblib")
        joblib.dump(FEATURE_COLUMNS, target / "features.joblib")
        (target / "metadata.json").write_text(
            json.dumps(
                {
                    "model_version": TINY_VERSION,
                    "selected_model": "rf-tiny",
                    "synthetic_only": True,
                    "seed": 7,
                    "features": FEATURE_COLUMNS,
                }
            ),
            encoding="utf-8",
        )
    finally:
        sys.path.remove(ml_dir)


@pytest.fixture(scope="session")
def tiny_model_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("tiny-model")
    _build_tiny_model(path)
    return path


@pytest.fixture(autouse=True)
def use_tiny_model(tiny_model_dir: Path):
    previous = os.environ.get("MEDQUEUE_MODEL_DIR")
    os.environ["MEDQUEUE_MODEL_DIR"] = str(tiny_model_dir)
    triage_model.reset_cache()
    try:
        yield
    finally:
        triage_model.reset_cache()
        if previous is None:
            os.environ.pop("MEDQUEUE_MODEL_DIR", None)
        else:
            os.environ["MEDQUEUE_MODEL_DIR"] = previous
