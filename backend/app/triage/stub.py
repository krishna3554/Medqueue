"""Deterministic triage placeholder until a validated model is available."""

from typing import Any

from app.triage.rules import MatchedRule, evaluate_rules


def stub_triage(
    symptoms: set[str], vitals: dict[str, Any], age: int | None, rules: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return the stable triage-result contract, enforcing rules-first precedence."""
    red_flags: list[MatchedRule] = evaluate_rules(symptoms, vitals, age, rules)
    if red_flags:
        return {
            "level": 1,
            "red_flag": True,
            "rules": red_flags,
            "factors": [rule.name for rule in red_flags],
            "source": "rules",
        }
    level = 4
    if vitals.get("temp_c", 0) >= 38.5 or vitals.get("pulse", 0) >= 110:
        level = 2
    elif vitals.get("sbp", 0) >= 160:
        level = 3
    return {"level": level, "red_flag": False, "rules": [], "factors": [], "source": "stub"}
