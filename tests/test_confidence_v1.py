import pytest
from intelligence.confidence import calculate_confidence


def test_adversarial_test_a_low_gap_confidence_cap():
    """Test A: Attraktiver Gap, aber low Gap Confidence (42) deckelt Gesamtergebnis"""
    case_input = {
        "gap_confidence": 42,
        "risk_assessment": {
            "evaluation_complete": True,
            "evaluation_status": {"mlc": "COMPLETE", "druckmuster": "COMPLETE", "hazard": "COMPLETE", "gf_mod_01": "COMPLETE"}
        },
        "liquidity_assessment": {
            "liquidity": "HIGH",
            "evaluation_status": {"market_activity": "COMPLETE", "time_to_exit": "COMPLETE", "demand": "COMPLETE"}
        },
        "n_usable_sources": 5,
        "contradiction_index": 0.0
    }
    res = calculate_confidence(case_input)["confidence_assessment"]
    assert res["confidence"] <= 42
    assert any(cap["rule"] == "low_gap_confidence_cap" for cap in res["active_caps"])


def test_adversarial_test_b_contradictory_sources():
    """Test B: Viele Quellen (12), aber hoher Widerspruchsindex (0.6)"""
    case_input = {
        "gap_confidence": 80,
        "risk_assessment": {
            "evaluation_complete": True,
            "evaluation_status": {"mlc": "COMPLETE", "druckmuster": "COMPLETE", "hazard": "COMPLETE", "gf_mod_01": "COMPLETE"}
        },
        "liquidity_assessment": {
            "liquidity": "HIGH",
            "evaluation_status": {"market_activity": "COMPLETE", "time_to_exit": "COMPLETE", "demand": "COMPLETE"}
        },
        "n_usable_sources": 12,
        "contradiction_index": 0.6
    }
    res = calculate_confidence(case_input)["confidence_assessment"]
    # 0.15 + 0.15*5 - 0.10*0.6 = 0.90 - 0.06 = 0.84
    assert res["components"]["evidence_sufficiency"] == 0.84


def test_adversarial_test_c_liquidity_unknown_cap():
    """Test C: Risk Vollständig, aber Liquidity = UNKNOWN -> Cap <= 40"""
    case_input = {
        "gap_confidence": 90,
        "risk_assessment": {
            "evaluation_complete": True,
            "evaluation_status": {"mlc": "COMPLETE", "druckmuster": "COMPLETE", "hazard": "COMPLETE", "gf_mod_01": "COMPLETE"}
        },
        "liquidity_assessment": {
            "liquidity": "UNKNOWN",
            "evaluation_status": {"market_activity": "COMPLETE", "time_to_exit": "INSUFFICIENT_DATA", "demand": "COMPLETE"}
        },
        "n_usable_sources": 5,
        "contradiction_index": 0.0
    }
    res = calculate_confidence(case_input)["confidence_assessment"]
    assert res["confidence"] <= 40
    assert any(cap["rule"] == "liquidity_unknown_cap" for cap in res["active_caps"])


def test_adversarial_test_d_minimal_sources():
    """Test D: Minimales Sample (1 Quelle)"""
    case_input = {
        "gap_confidence": 80,
        "risk_assessment": {
            "evaluation_complete": True,
            "evaluation_status": {"mlc": "COMPLETE", "druckmuster": "COMPLETE", "hazard": "COMPLETE", "gf_mod_01": "COMPLETE"}
        },
        "liquidity_assessment": {
            "liquidity": "HIGH",
            "evaluation_status": {"market_activity": "COMPLETE", "time_to_exit": "COMPLETE", "demand": "COMPLETE"}
        },
        "n_usable_sources": 1,
        "contradiction_index": 0.0
    }
    res = calculate_confidence(case_input)["confidence_assessment"]
    # evidence_sufficiency_norm = 0.15 + 0.15*1 = 0.30
    assert res["components"]["evidence_sufficiency"] == 0.30
    # raw_score = 100 * 0.8 * 1.0 * 1.0 * 0.3 = 24
    assert res["confidence"] == 24
