"""Application-level triage orchestration.

The service owns the ordering of the decision-support layers:

1. configured red-flag rules (always authoritative),
2. the optional trained model with an explanation, and
3. the deterministic stub when model artifacts are unavailable.

Keeping this policy out of the HTTP handlers makes it possible to exercise the
safety-critical precedence independently of persistence and transport code.
"""

from collections.abc import Callable
from typing import Any

from app.triage.rules import evaluate_rules
from app.triage.stub import stub_triage


def triage(
    symptoms: set[str],
    vitals: dict[str, Any],
    age: int | None,
    rules: list[dict[str, Any]],
    *,
    predictor: Callable[[set[str], dict[str, Any], int | None], dict[str, Any] | None],
    explainer: Callable[[set[str], dict[str, Any], int | None, int], dict[str, Any]],
) -> dict[str, Any]:
    """Return a normalized triage result using rules-first precedence.

    ``predictor`` and ``explainer`` are injected so callers can use the real
    model while tests can verify orchestration without loading model files.
    A model or explanation failure is treated as model unavailability and
    safely falls through to the deterministic stub.
    """
    normalized_symptoms = {
        str(item).strip().lower() for item in symptoms if str(item).strip()
    }

    matches = evaluate_rules(normalized_symptoms, vitals, age, rules)
    if matches:
        result = stub_triage(normalized_symptoms, vitals, age, rules)
        result["top_factors"] = None
        result["model_version"] = None
        return result

    try:
        predicted = predictor(normalized_symptoms, vitals, age)
        if predicted is not None:
            level = int(predicted["level"])
            if level not in range(1, 6):
                raise ValueError("model returned a triage level outside 1..5")
            details = explainer(normalized_symptoms, vitals, age, level)
            return {
                "level": level,
                "red_flag": False,
                "rules": [],
                "factors": [details["rationale"]],
                "source": "model",
                "top_factors": details["top_factors"],
                "model_version": str(predicted["model_version"]),
            }
    except Exception:  # noqa: BLE001 - optional AI must never block registration
        # Registration and triage must remain available if an optional AI
        # artifact is stale, malformed, or temporarily unable to explain.
        pass

    result = stub_triage(normalized_symptoms, vitals, age, rules)
    result["top_factors"] = None
    result["model_version"] = None
    return result
