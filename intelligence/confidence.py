"""
ALADIN37 — Confidence Score V1
Meta-Evidenz-Layer zur Berechnung der Verlässlichkeit der Entscheidungsgrundlage.
Kopplung: Multiplikative Aggregation aus Price Gap, Risk, Liquidity und Quellenbasisevidenz.
"""

from typing import Dict, Any, List, Optional

ENGINE_VERSION = "confidence_v1"

STATUS_FACTORS = {
    "COMPLETE": 1.00,
    "INSUFFICIENT_DATA": 0.40,
    "INVALID": 0.00
}


def calculate_confidence(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Berechnet die Confidence Assessment gemäß Spezifikation V1.
    """
    # 1. Daten-Extraktion
    gap_confidence = case_data.get("gap_confidence")
    risk_assessment = case_data.get("risk_assessment", {})
    liquidity_assessment = case_data.get("liquidity_assessment", {})
    
    n_usable_sources = case_data.get("n_usable_sources", 0)
    contradiction_index = case_data.get("contradiction_index", 0.0)

    # Validierung Fail-Closed
    if gap_confidence is None or not isinstance(gap_confidence, (int, float)):
        return _invalid_response("gap_confidence", "Missing or invalid gap_confidence value")

    # --- Component 1: Gap Confidence Norm ---
    gap_confidence_norm = max(0.0, min(1.0, float(gap_confidence) / 100.0))

    # --- Component 2: Risk Evidence Quality Norm ---
    risk_status_map = risk_assessment.get("evaluation_status", {})
    if not risk_status_map or any(v is None for v in risk_status_map.values()):
        return _invalid_response("risk_evidence_quality", "risk_assessment.evaluation_status contains null or missing values")

    risk_factors = []
    limiting_risk_cat = None
    min_risk_factor = 1.01

    for cat in ["mlc", "druckmuster", "hazard", "gf_mod_01"]:
        st = risk_status_map.get(cat, "INVALID")
        factor = STATUS_FACTORS.get(st, 0.0)
        risk_factors.append(factor)
        if factor < min_risk_factor:
            min_risk_factor = factor
            limiting_risk_cat = cat

    risk_evidence_quality_norm = min_risk_factor
    if risk_evidence_quality_norm == 0.0:
        return _invalid_response("risk_evidence_quality", f"Risk component {limiting_risk_cat} is INVALID")

    # --- Component 3: Liquidity Evidence Quality Norm ---
    liq_status_map = liquidity_assessment.get("evaluation_status", {})
    if not liq_status_map or any(v is None for v in liq_status_map.values()):
        return _invalid_response("liquidity_evidence_quality", "liquidity_assessment.evaluation_status contains null or missing values")

    liq_factors = []
    limiting_liq_cat = None
    min_liq_factor = 1.01

    for cat in ["market_activity", "time_to_exit", "demand"]:
        st = liq_status_map.get(cat, "INVALID")
        factor = STATUS_FACTORS.get(st, 0.0)
        liq_factors.append(factor)
        if factor < min_liq_factor:
            min_liq_factor = factor
            limiting_liq_cat = cat

    liquidity_evidence_quality_norm = min_liq_factor
    if liquidity_evidence_quality_norm == 0.0:
        return _invalid_response("liquidity_evidence_quality", f"Liquidity component {limiting_liq_cat} is INVALID")

    # --- Component 4: Evidence Sufficiency Norm ---
    capped_sources = min(int(n_usable_sources), 5)
    evidence_sufficiency_norm = 0.15 + (0.15 * capped_sources) - (0.10 * float(contradiction_index))
    evidence_sufficiency_norm = max(0.0, min(1.0, evidence_sufficiency_norm))

    # --- Multiplikation ---
    raw_score = 100.0 * (
        gap_confidence_norm
        * risk_evidence_quality_norm
        * liquidity_evidence_quality_norm
        * evidence_sufficiency_norm
    )

    # --- Hard Caps Prüfen ---
    active_caps = []
    binding_caps = []

    # Cap 1: Risk Complete
    risk_complete = risk_assessment.get("evaluation_complete", False)
    if not risk_complete:
        active_caps.append({"rule": "risk_incomplete_cap", "value": 30, "note": "Risk calculation incomplete"})

    # Cap 2: Liquidity Unknown
    liquidity_label = liquidity_assessment.get("liquidity", "UNKNOWN")
    if liquidity_label == "UNKNOWN":
        active_caps.append({"rule": "liquidity_unknown_cap", "value": 40, "note": "Liquidity assessment is UNKNOWN"})

    # Cap 3: Low Gap Confidence
    if gap_confidence < 50:
        active_caps.append({"rule": "low_gap_confidence_cap", "value": gap_confidence, "note": f"Gap confidence {gap_confidence} < 50"})

    # Anwendung Caps via MIN
    final_score = raw_score
    for cap in active_caps:
        cap_val = cap["value"]
        if final_score > cap_val:
            final_score = float(cap_val)
            cap["binding"] = True
        else:
            cap["binding"] = False

    return {
        "confidence_assessment": {
            "confidence": int(round(final_score)),
            "confidence_status": "COMPLETE",
            "components": {
                "gap_confidence": gap_confidence,
                "risk_evidence_quality": risk_evidence_quality_norm,
                "liquidity_evidence_quality": liquidity_evidence_quality_norm,
                "evidence_sufficiency": round(evidence_sufficiency_norm, 4)
            },
            "component_basis": {
                "risk_evidence_quality": {
                    "limiting_category": limiting_risk_cat,
                    "status": risk_status_map.get(limiting_risk_cat)
                },
                "liquidity_evidence_quality": {
                    "limiting_category": limiting_liq_cat,
                    "status": liq_status_map.get(limiting_liq_cat)
                }
            },
            "active_caps": active_caps,
            "raw_multiplicative_score": round(raw_score, 2),
            "n_usable_sources": n_usable_sources,
            "contradiction_index": contradiction_index,
            "engine_version": ENGINE_VERSION
        }
    }


def _invalid_response(invalid_component: str, reason: str) -> Dict[str, Any]:
    return {
        "confidence_assessment": {
            "confidence": 0,
            "confidence_status": "INVALID",
            "invalid_component": invalid_component,
            "reason": reason,
            "engine_version": ENGINE_VERSION
        }
    }
