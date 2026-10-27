from app.triage.service import triage


RULES = [
    {
        "id": "RF",
        "name": "Low oxygen",
        "all": [{"vital": {"spo2": {"lt": 92}}}],
    }
]


def test_red_flag_rules_precede_model() -> None:
    result = triage(
        {"chest_pain"},
        {"spo2": 90},
        40,
        RULES,
        predictor=lambda *_: {"level": 5, "model_version": "test"},
        explainer=lambda *_: {"rationale": "model", "top_factors": []},
    )

    assert result["source"] == "rules"
    assert result["level"] == 1
    assert result["red_flag"] is True


def test_model_result_has_explanation() -> None:
    result = triage(
        set(),
        {},
        None,
        RULES,
        predictor=lambda *_: {"level": 3, "model_version": "test-1"},
        explainer=lambda *_: {
            "rationale": "Stable presentation",
            "top_factors": [{"name": "age", "value": 30, "contribution": 0.1}],
        },
    )

    assert result["source"] == "model"
    assert result["factors"] == ["Stable presentation"]
    assert result["model_version"] == "test-1"


def test_invalid_model_falls_back_to_stub() -> None:
    result = triage(
        set(),
        {"temp_c": 39},
        None,
        RULES,
        predictor=lambda *_: {"level": 9, "model_version": "bad"},
        explainer=lambda *_: {"rationale": "never used", "top_factors": []},
    )

    assert result["source"] == "stub"
    assert result["level"] == 2
    assert result["model_version"] is None
