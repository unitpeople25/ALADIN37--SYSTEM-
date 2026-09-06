"""
ALADIN37 — Decision Engine V1 & Decision Integrity Gate V1.1
Synthetisiert Price Gap, Risk Level, Liquidity und Confidence in den finalen DECISION_STATUS.
"""

from typing import Dict, Any, List, Optional

ENGINE_VERSION = "decision_v1"


def evaluate_decision_gate(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decision Integrity Gate V1 + V1.1
    Prüft Vollständigkeit der Evidenz, Red Flags und IN_PRUEFUNG-Trigger.
    """
    price_gap_assessment = case_data.get("price_gap_assessment", {})
    risk_assessment = case_data.get("risk_assessment", {})
    confidence_assessment = case_data.get("confidence_assessment", {})

    # Gate V1.1: confidence_status == INVALID -> BLOCK
    conf_status = confidence_assessment.get("confidence_status")
    if conf_status == "INVALID":
        return {
            "gate_result": "BLOCK",
            "reason": f"Confidence Assessment is INVALID ({confidence_assessment.get("reason", "Unknown")})",
            "in_pruefung_triggers": [],
            "red_flags": []
        }

    # Pflicht-Inputs
    market_value_eur = price_gap_assessment.get("market_value_eur")
    risk_level = risk_assessment.get("risk_level")

    if market_value_eur is None or risk_level is None:
        return {
            "gate_result": "BLOCK",
            "reason": "Missing mandatory inputs (market_value_eur or risk_level)",
            "in_pruefung_triggers": [],
            "red_flags": []
        }

    in_pruefung_triggers = []
    red_flags = []

    # Trigger-Checks
    mikrosegment_count = price_gap_assessment.get("mikrosegment_match_count", 0)
    if mikrosegment_count < 2:
        in_pruefung_triggers.append("MIKROSEGMENT_MATCH_LESS_THAN_2")

    gap_confidence = price_gap_assessment.get("gap_confidence", 0)
    if gap_confidence < 50:
        in_pruefung_triggers.append("GAP_CONFIDENCE_BELOW_50")

    residual_gap_pct = price_gap_assessment.get("residual_gap_pct", 0.0)
    if residual_gap_pct > 0.20:
        in_pruefung_triggers.append("UNEXPLAINED_RESIDUAL_GAP_ABOVE_20_PCT")

    rechtsstatus_geprueft = case_data.get("rechtsstatus_geprueft", True)
    if not rechtsstatus_geprueft:
        in_pruefung_triggers.append("RECHTSSTATUS_NICHT_GEPRUEFT")

    risk_eval_complete = risk_assessment.get("evaluation_complete", False)
    if not risk_eval_complete:
        in_pruefung_triggers.append("RISK_ASSESSMENT_INCOMPLETE")

    # Red Flags
    mlc_flags = risk_assessment.get("flags", [])
    if "MLC-010" in mlc_flags:
        red_flags.append("MLC-010_PARTICULAR_MASKING")

    if "MLC-011" in mlc_flags:
        in_pruefung_triggers.append("MLC-011_UNSPECIFIED_LIEN_CLAUSE")

    hazard_flags = case_data.get("hazard_flags", [])
    if "LEY_DE_COSTAS_UNQUALIFIED" in hazard_flags:
        red_flags.append("LEY_DE_COSTAS_UNQUALIFIED")

    return {
        "gate_result": "PASS",
        "reason": "Gate checks executed successfully",
        "in_pruefung_triggers": in_pruefung_triggers,
        "red_flags": red_flags
    }


def calculate_decision(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decision Engine V1 Hauptfunktion
    """
    gate_output = evaluate_decision_gate(case_data)
    gate_result = gate_output["gate_result"]
    in_pruefung_triggers = gate_output["in_pruefung_triggers"]
    red_flags = gate_output["red_flags"]

    price_gap_assessment = case_data.get("price_gap_assessment", {})
    risk_assessment = case_data.get("risk_assessment", {})
    liquidity_assessment = case_data.get("liquidity_assessment", {})
    confidence_assessment = case_data.get("confidence_assessment", {})

    risk_level = risk_assessment.get("risk_level", "CRITICAL")
    price_gap_status = price_gap_assessment.get("status", "INSUFFICIENT_DATA")
    gap_confidence = price_gap_assessment.get("gap_confidence", 0)
    confidence = confidence_assessment.get("confidence", 0)
    liquidity = liquidity_assessment.get("liquidity", "UNKNOWN")

    # Schritt 1: GATE_RESULT = BLOCK?
    if gate_result == "BLOCK":
        return _decision_response("IN_PRUEFUNG", f"GATE_BLOCKED: {gate_output["reason"]}", gate_output)

    # Schritt 2: RISK_LEVEL = CRITICAL?
    if risk_level == "CRITICAL":
        return _decision_response("REJECT", "RISK_LEVEL_IS_CRITICAL", gate_output)

    # Schritt 3: IN_PRUEFUNG-Trigger aktiv?
    if len(in_pruefung_triggers) > 0:
        return _decision_response("IN_PRUEFUNG", f"TRIGGERED_BY_{in_pruefung_triggers[0]}", gate_output)

    # Schritt 4: Red Flag aktiv?
    has_red_flags = len(red_flags) > 0

    # Schritt 5: BUY_CANDIDATE Hard Constraint
    buy_candidate_eligible = (
        gate_result == "PASS"
        and risk_level != "CRITICAL"
        and not has_red_flags
        and len(in_pruefung_triggers) == 0
        and price_gap_status != "INSUFFICIENT_DATA"
        and gap_confidence >= 60
        and confidence >= 55
        and liquidity != "UNKNOWN"
    )

    if buy_candidate_eligible:
        return _decision_response("BUY_CANDIDATE", "ALL_HARD_CONSTRAINTS_MET", gate_output)

    # Schritt 6: Sonst WATCH
    reason = "RED_FLAG_ACTIVE" if has_red_flags else "BUY_CONSTRAINT_NOT_MET"
    if not has_red_flags:
        if gap_confidence < 60:
            reason = f"GAP_CONFIDENCE_BELOW_THRESHOLD ({gap_confidence} < 60)"
        elif confidence < 55:
            reason = f"CONFIDENCE_BELOW_THRESHOLD ({confidence} < 55)"
        elif liquidity == "UNKNOWN":
            reason = "LIQUIDITY_IS_UNKNOWN"

    return _decision_response("WATCH", reason, gate_output)


def _decision_response(status: str, reason: str, gate_output: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "decision": {
            "decision_status": status,
            "decision_reason": reason,
            "gate_evaluation": gate_output,
            "engine_version": ENGINE_VERSION
        }
    }
