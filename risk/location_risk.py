"""
ALADIN37 - Location Risk Engine
Phase 5 / Risk-Modul

Heuristik-Start. market_average/premium_zones-Listen sind bewusst als
austauschbare Konstanten gehalten, damit sie später aus PostGIS/IGN-Daten
befüllt werden können, ohne die Aufrufer anzufassen.

Rückgabe: risk_points (0-100, höher = schwächere Lage) + Flags.
"""

PREMIUM_ZONES = {
    "port andratx", "santa ponsa", "santa ponça", "puerto portals",
    "portals nous", "son vida", "deia", "valldemossa", "camp de mar",
}

FLOOD_OR_COASTAL_LEGAL_RISK_ZONES = {
    # Zonen mit bekannter Ley-de-Costas-/Überschwemmungsproblematik -
    # Platzhalterliste, in Produktion mit AEMET/IGN-Layer abgleichen.
}


def assess(listing: dict) -> dict:
    city = (listing.get("city") or "").strip().lower()
    location_class = listing.get("location_class")  # z.B. "frontline" aus normalizer.py

    risk = 0
    flags = []

    if city not in PREMIUM_ZONES:
        risk += 20
        flags.append("P-04 Lage außerhalb bekannter Premium-Zonen")

    if city in FLOOD_OR_COASTAL_LEGAL_RISK_ZONES:
        risk += 25
        flags.append("MLC-006 Zone mit bekanntem Ley-de-Costas-/Hochwasserrisiko")

    if location_class == "frontline" and city in FLOOD_OR_COASTAL_LEGAL_RISK_ZONES:
        # Erste Meereslinie in Risikozone = zusätzliche rechtliche Prüfpflicht
        risk += 15
        flags.append("MLC-007 Erste Meereslinie in Ley-de-Costas-Risikozone")

    if not city:
        risk += 10
        flags.append("R-014 Ort nicht identifizierbar")

    return {
        "risk_points": min(risk, 100),
        "is_premium_zone": city in PREMIUM_ZONES,
        "flags": flags,
    }
