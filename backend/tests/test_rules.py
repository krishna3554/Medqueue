from pathlib import Path

import pytest

from app.triage.rules import RuleConfigurationError, evaluate_rules, load_rules
from app.triage.stub import stub_triage

RULES = load_rules(Path(__file__).parents[2] / "docs" / "red_flag_rules.yaml")


@pytest.mark.parametrize(
    ("symptoms", "vitals", "age", "rule_id"),
    [
        ({"chest_pain"}, {"spo2": 91}, 40, "RF01"),
        ({"chest_tightness", "breathlessness"}, {}, 40, "RF02"),
        (set(), {"spo2": 89}, 40, "RF03"),
        (set(), {"sbp": 200}, 40, "RF04"),
        ({"confusion"}, {}, 40, "RF05"),
        ({"slurred_speech"}, {}, 40, "RF06"),
        ({"heavy_bleeding"}, {}, 40, "RF07"),
        (set(), {"temp_c": 39}, 75, "RF08"),
    ],
)
def test_each_rule_has_a_positive_case(symptoms, vitals, age, rule_id) -> None:
    assert rule_id in {match.id for match in evaluate_rules(symptoms, vitals, age, RULES)}


@pytest.mark.parametrize(
    ("symptoms", "vitals", "age", "rule_id"),
    [
        ({"chest_pain"}, {"spo2": 92}, 40, "RF01"),
        ({"chest_pain"}, {}, 40, "RF02"),
        (set(), {"spo2": 90}, 40, "RF03"),
        (set(), {"sbp": 199}, 40, "RF04"),
        ({"headache"}, {}, 40, "RF05"),
        ({"dizziness"}, {}, 40, "RF06"),
        ({"light_bleeding"}, {}, 40, "RF07"),
        (set(), {"temp_c": 39}, 40, "RF08"),
    ],
)
def test_each_rule_has_a_negative_case(symptoms, vitals, age, rule_id) -> None:
    assert rule_id not in {match.id for match in evaluate_rules(symptoms, vitals, age, RULES)}


def test_missing_vitals_are_unknown_not_normal() -> None:
    assert evaluate_rules({"chest_pain"}, {}, 40, RULES) == []


@pytest.mark.parametrize(
    "content",
    ["rules: [not-a-rule]", "rules:\n  - id: RF99\n    name: Bad\n    vital: {spo2: {equals: 92}}"],
)
def test_malformed_yaml_fails_loudly(tmp_path: Path, content: str) -> None:
    invalid = tmp_path / "rules.yaml"
    invalid.write_text(content, encoding="utf-8")
    with pytest.raises(RuleConfigurationError):
        load_rules(invalid)


def test_stub_enforces_rule_precedence_and_contract() -> None:
    result = stub_triage({"chest_pain"}, {"spo2": 91, "temp_c": 36}, 40, RULES)
    assert result["level"] == 1
    assert result["red_flag"] is True
    assert result["source"] == "rules"
    assert result["rules"][0].name == "Chest symptoms with low oxygen"
