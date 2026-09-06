import pytest
from intelligence.decision import calculate_decision


def test_decision_chain_buy_candidate():
    """Valider Buy Candidate: Alle Schwellen erfüllt"""
    case_input = {
        "price_gap_assessment": {
            "market_value_eur": 500000,
            "status": "VALID",
            "gap_confidence": 75,
            "mikrosegment_match_count": 4,
            "residual_gap_pct": 0.05
        },
        "risk_assessment": {
            "risk_level": "LOW",
            "evaluation_complete": True,
            "flags": []
        },
        "liquidity_assessment": {
            "liquidity": "HIGH"
        },
        "confidence_assessment": {
            "confidence": 68,
            "confidence_status": "COMPLETE"
        },
        "rechtsstatus_geprueft": True
    }
    res = calculate_decision(case_input)["decision"]
    assert res["decision_status"] == "BUY_CANDIDATE"


def test_decision_chain_reject_on_critical_risk():
    """Critical Risk überschreibt hohe Attraktivität -> REJECT"""
    case_input = {
        "price_gap_assessment": {
            "market_value_eur": 500000,
            "status": "VALID",
            "gap_confidence": 90,
            "mikrosegment_match_count": 5
        },
        "risk_assessment": {
            "risk_level": "CRITICAL",
            "evaluation_complete": True,
            "flags": []
        },
        "liquidity_assessment": {"liquidity": "HIGH"},
        "confidence_assessment": {"confidence": 85, "confidence_status": "COMPLETE"},
        "rechtsstatus_geprueft": True
    }
    res = calculate_decision(case_input)["decision"]
    assert res["decision_status"] == "REJECT"


def test_decision_chain_in_pruefung_on_low_gap_conf():
    """Gap Confidence < 50 erzeugt IN_PRUEFUNG"""
    case_input = {
        "price_gap_assessment": {
            "market_value_eur": 500000,
            "status": "VALID",
            "gap_confidence": 45,
            "mikrosegment_match_count": 3
        },
        "risk_assessment": {
            "risk_level": "LOW",
            "evaluation_complete": True,
            "flags": []
        },
        "liquidity_assessment": {"liquidity": "HIGH"},
        "confidence_assessment": {"confidence": 40, "confidence_status": "COMPLETE"},
        "rechtsstatus_geprueft": True
    }
    res = calculate_decision(case_input)["decision"]
    assert res["decision_status"] == "IN_PRUEFUNG"


def test_decision_chain_gate_v1_1_block_invalid_confidence():
    """Gate V1.1: confidence_status == INVALID blockiert und erzwingt IN_PRUEFUNG"""
    case_input = {
        "price_gap_assessment": {
            "market_value_eur": 500000,
            "status": "VALID",
            "gap_confidence": 75,
            "mikrosegment_match_count": 4
        },
        "risk_assessment": {
            "risk_level": "LOW",
            "evaluation_complete": True,
            "flags": []
        },
        "liquidity_assessment": {"liquidity": "HIGH"},
        "confidence_assessment": {
            "confidence": 0,
            "confidence_status": "INVALID",
            "reason": "liquidity_assessment status invalid"
        },
        "rechtsstatus_geprueft": True
    }
    res = calculate_decision(case_input)["decision"]
    assert res["decision_status"] == "IN_PRUEFUNG"
    assert "GATE_BLOCKED" in res["decision_reason"]
