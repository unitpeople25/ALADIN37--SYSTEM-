"""
ALADIN37 - Scoring Engine
Phase 5 / Modul 4

Kombiniert die drei Risk-Engine-Module zu den vier ALADIN37-Hauptscores
und berechnet den Gesamtscore:

    total = location*0.30 + price_risk*0.30 + rental*0.20 + broker*0.20

Hinweis zur Formel: PRICE RISK fließt hier bewusst als Risiko-Score
(höher = teurer/riskanter) direkt in die Summe ein - so wie im
ALADIN37-Referenzbeispiel (Lage 82, Preisrisiko 67, Vermietbarkeit 78,
Maklertransparenz 54 -> Gesamt 71). Der Gesamtscore ist also kein reiner
"je höher desto besser"-Wert, sondern ein Entscheidungs-Indexscore, den
die Decision Layer interpretiert (siehe pipeline.py).
"""

from risk import price_risk, location_risk, broker_risk

WEIGHTS = {
    "location": 0.30,
    "price_risk": 0.30,
    "rental": 0.20,
    "broker": 0.20,
}

# Rental-Potenzial-Heuristik (kein eigenes Risk-Modul laut Architekturvorgabe,
# lebt direkt in der Scoring Engine).
RENTAL_DEMAND_ZONES = {
    "santa ponsa": 85, "santa ponça": 85, "port andratx": 90,
    "puerto portals": 90, "palma": 70, "calvia": 75, "calvià": 75,
}
FALLBACK_RENTAL_DEMAND = 55


def _rental_score(normalized: dict) -> dict:
    city = (normalized.get("city") or "").strip().lower()
    base = RENTAL_DEMAND_ZONES.get(city, FALLBACK_RENTAL_DEMAND)

    score = base
    notes = []

    if normalized.get("has_rental_license") is True:
        score += 10
        notes.append("Ferienvermietlizenz vorhanden")
    elif normalized.get("has_rental_license") is False:
        score -= 20
        notes.append("Keine Ferienvermietlizenz - schränkt kurzfristige Vermietung ein")

    if normalized.get("sea_view"):
        score += 5
        notes.append("Meerblick erhöht Vermietbarkeit")

    if normalized.get("condition") == "needs_renovation":
        score -= 10
        notes.append("Renovierungsbedarf senkt kurzfristige Vermietbarkeit")

    score = max(0, min(100, score))
    return {"score": score, "notes": notes}


def score_listing(listing: dict, normalized: dict, broker_history: dict = None) -> dict:
    """
    listing: Rohdaten aus der DB/Extraction (enthält u.a. price, city, _raw_text)
    normalized: Ergebnis von intelligence/normalizer.py

    Gibt die vier Hauptscores, den Gesamtscore, sowie alle gesammelten
    Risiko-Flags (für die Decision Layer / Ausgabe) zurück.
    """
    price_result = price_risk.assess({**listing, **normalized})
    location_result = location_risk.assess(normalized)
    broker_result = broker_risk.assess(listing, normalized, broker_history=broker_history)
    rental_result = _rental_score(normalized)

    location_score = max(0, 100 - location_result["risk_points"])
    price_risk_score = max(0, 100 - price_result["risk_points"])
    broker_score = max(0, 100 - broker_result["risk_points"])
    rental_score = rental_result["score"]

    total = (
        location_score * WEIGHTS["location"]
        + price_risk_score * WEIGHTS["price_risk"]
        + rental_score * WEIGHTS["rental"]
        + broker_score * WEIGHTS["broker"]
    )

    all_flags = (
        location_result["flags"]
        + price_result["flags"]
        + broker_result["flags"]
    )

    return {
        "location_score": round(location_score, 1),
        "price_risk_score": round(price_risk_score, 1),
        "rental_score": round(rental_score, 1),
        "broker_score": round(broker_score, 1),
        "total_score": round(total, 1),
        "flags": all_flags,
        "details": {
            "price": price_result,
            "location": location_result,
            "broker": broker_result,
            "rental": rental_result,
        },
    }
