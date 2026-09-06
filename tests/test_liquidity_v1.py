import pytest
from intelligence.liquidity import calculate_liquidity


def test_adversarial_case_insufficient_exit_data():
    """
    Testfall aus Abschnitt 6 der Spezifikation:
    Hohe Marktaktivität (90), aber nur 1 Exit-Fall -> Zwingend UNKNOWN.
    """
    case_input = {
        "liquidity_input": {
            "comparable_transactions": [1, 2, 3, 4],
            "closed_exit_cases": [45],
            "demand_observation_periods": 1,
            "market_activity_raw_score": 90,
            "demand_raw_score": 70
        }
    }

    result = calculate_liquidity(case_input)["liquidity_assessment"]

    assert result["liquidity_score"] is None
    assert result["liquidity"] == "UNKNOWN"
    assert result["evaluation_status"]["time_to_exit"] == "INSUFFICIENT_DATA"
    assert "closed_exit_cases_below_minimum" in result["missing_required_data"]


def test_complete_valid_liquidity_medium():
    """
    Vollständiger Fall mit validen Samples -> MEDIUM / HIGH
    """
    case_input = {
        "liquidity_input": {
            "comparable_transactions": [101, 102, 103, 104, 105],
            "closed_exit_cases": [60, 65, 70],
            "demand_observation_periods": 2,
            "market_activity_raw_score": 62,
            "demand_raw_score": 61
        }
    }

    result = calculate_liquidity(case_input)["liquidity_assessment"]

    assert result["liquidity_score"] is not None
    assert result["liquidity"] in ["MEDIUM", "HIGH"]
    assert result["evaluation_status"]["market_activity"] == "COMPLETE"
    assert result["evaluation_status"]["time_to_exit"] == "COMPLETE"
    assert len(result["missing_required_data"]) == 0
