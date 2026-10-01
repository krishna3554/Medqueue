"""Config-driven red-flag rule evaluation for prototype triage."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class MatchedRule:
    id: str
    name: str


class RuleConfigurationError(ValueError):
    """Raised when a red-flag rule configuration is malformed."""


def load_rules(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate a YAML rule file before it is used for triage."""
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RuleConfigurationError(f"could not load red-flag rules: {error}") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("rules"), list):
        raise RuleConfigurationError("rule file must contain a 'rules' list")

    validated: list[dict[str, Any]] = []
    for rule in raw["rules"]:
        if (
            not isinstance(rule, dict)
            or not isinstance(rule.get("id"), str)
            or not isinstance(rule.get("name"), str)
        ):
            raise RuleConfigurationError("every rule requires string 'id' and 'name'")
        if set(rule).isdisjoint({"all", "any"}):
            raise RuleConfigurationError(f"rule {rule['id']} requires 'all' or 'any'")
        _validate_condition(
            {key: value for key, value in rule.items() if key not in {"id", "name"}}
        )
        validated.append(rule)
    return validated


def _validate_condition(condition: Any) -> None:
    if not isinstance(condition, dict):
        raise RuleConfigurationError("rule condition must be a mapping")
    known = {"all", "any", "symptom_any", "vital", "age"}
    if set(condition) - known:
        raise RuleConfigurationError("rule condition contains an unsupported operator")
    for group in ("all", "any"):
        if group in condition:
            if not isinstance(condition[group], list) or not condition[group]:
                raise RuleConfigurationError(f"'{group}' must be a non-empty list")
            for item in condition[group]:
                _validate_condition(item)
    if "symptom_any" in condition and (
        not isinstance(condition["symptom_any"], list)
        or not all(isinstance(item, str) for item in condition["symptom_any"])
    ):
        raise RuleConfigurationError("symptom_any must be a list of strings")
    if "vital" in condition:
        vitals = condition["vital"]
        if not isinstance(vitals, dict) or not vitals:
            raise RuleConfigurationError("vital must be a non-empty mapping")
        for comparison in vitals.values():
            _validate_comparison(comparison)
    if "age" in condition:
        _validate_comparison(condition["age"])


def _validate_comparison(comparison: Any) -> None:
    if not isinstance(comparison, dict) or not comparison:
        raise RuleConfigurationError("comparison must be a non-empty mapping")
    if "or" in comparison:
        if set(comparison) != {"or"} or not isinstance(comparison["or"], list):
            raise RuleConfigurationError("comparison 'or' must contain a list")
        for choice in comparison["or"]:
            _validate_comparison(choice)
        return
    if set(comparison) - {"lt", "lte", "gt", "gte"}:
        raise RuleConfigurationError("comparison contains an unsupported operator")
    if not all(isinstance(threshold, (int, float)) for threshold in comparison.values()):
        raise RuleConfigurationError("comparison thresholds must be numeric")


def _matches_comparison(value: float | int | None, comparison: dict[str, Any]) -> bool:
    if value is None:
        return False
    if "or" in comparison:
        choices = comparison["or"]
        return isinstance(choices, list) and any(
            isinstance(choice, dict) and _matches_comparison(value, choice) for choice in choices
        )
    for operator, threshold in comparison.items():
        if not isinstance(threshold, (int, float)):
            raise RuleConfigurationError("comparison thresholds must be numeric")
        if operator == "lt" and not value < threshold:
            return False
        if operator == "lte" and not value <= threshold:
            return False
        if operator == "gt" and not value > threshold:
            return False
        if operator == "gte" and not value >= threshold:
            return False
        if operator not in {"lt", "lte", "gt", "gte"}:
            raise RuleConfigurationError(f"unsupported comparison operator: {operator}")
    return bool(comparison)


def _matches(
    condition: dict[str, Any], symptoms: set[str], vitals: dict[str, Any], age: int | None
) -> bool:
    if "all" in condition and not all(
        _matches(item, symptoms, vitals, age) for item in condition["all"]
    ):
        return False
    if "any" in condition and not any(
        _matches(item, symptoms, vitals, age) for item in condition["any"]
    ):
        return False
    if "symptom_any" in condition and not symptoms.intersection(condition["symptom_any"]):
        return False
    if "vital" in condition:
        for vital, comparison in condition["vital"].items():
            value = vitals.get(vital)
            if not isinstance(value, (int, float)) or not _matches_comparison(value, comparison):
                return False
    if "age" in condition and not _matches_comparison(age, condition["age"]):
        return False
    return True


def evaluate_rules(
    symptoms: set[str], vitals: dict[str, Any], age: int | None, rules: list[dict[str, Any]]
) -> list[MatchedRule]:
    """Return all draft red-flag rules that match known patient information."""
    return [
        MatchedRule(id=rule["id"], name=rule["name"])
        for rule in rules
        if _matches(rule, symptoms, vitals, age)
    ]
