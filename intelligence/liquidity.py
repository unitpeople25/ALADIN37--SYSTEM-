"""
ALADIN37 — Liquidity Engine V1
Modul zur Berechnung der Exit- und Marktfähigkeit (LIQUIDITY).
Kopplung: Orthogonal zu RISK_LEVEL und PRICE_GAP.
"""

from typing import Dict, Any, List, Optional
import statistics
import math

ENGINE_VERSION = "liquidity_v1"

# Mindestsample-Vorgaben gemäß Spezifikation
MIN_COMPARABLE_TRANSACTIONS = 3
MIN_CLOSED_EXIT_CASES = 2
MIN_DEMAND_PERIODS = 1

# Gewichte
WEIGHT_MARKET_ACTIVITY = 0.35
WEIGHT_TIME_TO_EXIT = 0.40
WEIGHT_DEMAND = 0.25


def calculate_liquidity(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Berechnet die Liquidity Assessment auf Basis strukturierter Eingangsdaten.
    """
    liquidity_data = case_data.get("liquidity_input", {})
    
    comparable_tx = liquidity_data.get("comparable_transactions", [])
    closed_exits = liquidity_data.get("closed_exit_cases", [])
    demand_periods = liquidity_data.get("demand_observation_periods", 0)

    sample_sizes = {
        "comparable_transactions": len(comparable_tx),
        "closed_exit_cases": len(closed_exits),
        "demand_observation_periods": demand_periods
    }

    evaluation_status = {}
    component_scores = {}
    missing_required_data = []

    # --- Component 1: Market Activity ---
    if len(comparable_tx) >= MIN_COMPARABLE_TRANSACTIONS:
        component_scores["market_activity"] = liquidity_data.get("market_activity_raw_score")
        evaluation_status["market_activity"] = "COMPLETE"
    else:
        component_scores["market_activity"] = None
        evaluation_status["market_activity"] = "INSUFFICIENT_DATA"
        missing_required_data.append("comparable_transactions_below_minimum")

    # --- Component 2: Time-to-Exit ---
    if len(closed_exits) >= MIN_CLOSED_EXIT_CASES:
        tts_values = [float(x) for x in closed_exits]
        
        # Pure Python Varianz & IQR Prüfung (> 1.5 * IQR -> Median)
        quantiles = statistics.quantiles(tts_values, n=4) if len(tts_values) >= 2 else [tts_values[0]]*3
        q25, q75 = quantiles[0], quantiles[2]
        iqr = q75 - q25
        
        std_dev = statistics.stdev(tts_values) if len(tts_values) > 1 else 0.0
        
        if iqr > 0 and std_dev > (1.5 * iqr):
            effective_tts = float(statistics.median(tts_values))
        else:
            effective_tts = float(statistics.mean(tts_values))
            
        tts_score = max(0, min(100, int(100 - ((effective_tts - 30) / 150.0) * 100)))
        component_scores["time_to_exit"] = tts_score
        evaluation_status["time_to_exit"] = "COMPLETE"
    else:
        component_scores["time_to_exit"] = None
        evaluation_status["time_to_exit"] = "INSUFFICIENT_DATA"
        missing_required_data.append("closed_exit_cases_below_minimum")

    # --- Component 3: Demand / Absorption ---
    if demand_periods >= MIN_DEMAND_PERIODS and "demand_raw_score" in liquidity_data:
        component_scores["demand"] = liquidity_data.get("demand_raw_score")
        evaluation_status["demand"] = "COMPLETE"
    else:
        component_scores["demand"] = None
        evaluation_status["demand"] = "INSUFFICIENT_DATA"
        missing_required_data.append("demand_periods_below_minimum")

    # --- Aggregation & Evaluation ---
    all_complete = all(status == "COMPLETE" for status in evaluation_status.values())

    if not all_complete:
        liquidity_score = None
        liquidity_label = "UNKNOWN"
    else:
        calc_score = (
            WEIGHT_MARKET_ACTIVITY * component_scores["market_activity"] +
            WEIGHT_TIME_TO_EXIT * component_scores["time_to_exit"] +
            WEIGHT_DEMAND * component_scores["demand"]
        )
        liquidity_score = int(round(calc_score))
        
        if liquidity_score <= 33:
            liquidity_label = "LOW"
        elif liquidity_score <= 66:
            liquidity_label = "MEDIUM"
        else:
            liquidity_label = "HIGH"

    return {
        "liquidity_assessment": {
            "liquidity_score": liquidity_score,
            "liquidity": liquidity_label,
            "component_scores": component_scores,
            "sample_sizes": sample_sizes,
            "evaluation_status": evaluation_status,
            "missing_required_data": missing_required_data,
            "engine_version": ENGINE_VERSION
        }
    }
