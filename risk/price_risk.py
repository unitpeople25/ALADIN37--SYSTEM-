"""
ALADIN37 - Price Risk Engine
Phase 5 / Risk-Modul

Startet als Heuristik (Platzhalter-Marktdurchschnitte), ist aber so gebaut,
dass market_average später aus einer echten Vergleichsdaten-Tabelle
(z.B. Idealista-Marktstatistik pro Zone) kommen kann, ohne dass sich die
Aufrufer (scoring.py) ändern müssen.

Rückgabe: risk_points (0-100, höher = teurer/überbewerteter) + Flags.
"""

# Platzhalter: €/m²-Durchschnitte je Zone. In Produktion aus DB/API ersetzen.
DEFAULT_MARKET_AVERAGE_SQM = {
    "santa ponsa": 5200,
    "santa ponça": 5200,
    "port andratx": 9500,
    "palma": 4800,
    "calvia": 6000,
    "calvià": 6000,
}

FALLBACK_MARKET_AVERAGE_SQM = 5000

OVERPRICE_THRESHOLD = 1.25   # 25% über Marktschnitt -> starker Risikoaufschlag
MILD_OVERPRICE_THRESHOLD = 1.10  # 10% über Marktschnitt -> moderater Aufschlag


def assess(listing: dict, market_average_override: float = None) -> dict:
    price = listing.get("price")
    living_area = listing.get("living_area")
    city = (listing.get("city") or "").strip().lower()

    flags = []

    if not price or not living_area:
        return {
            "risk_points": 50,  # unbekannt -> neutral-vorsichtig, nicht 0
            "sqm_price": None,
            "market_average": None,
            "flags": ["R-001 Preis oder Fläche fehlt - keine belastbare Bewertung"],
        }

    sqm_price = price / living_area
    market_average = (
        market_average_override
        or DEFAULT_MARKET_AVERAGE_SQM.get(city, FALLBACK_MARKET_AVERAGE_SQM)
    )

    risk = 0

    if sqm_price > market_average * OVERPRICE_THRESHOLD:
        risk += 30
        flags.append("R-010 Preis >25% über Marktdurchschnitt")
    elif sqm_price > market_average * MILD_OVERPRICE_THRESHOLD:
        risk += 15
        flags.append("R-011 Preis >10% über Marktdurchschnitt")

    if not market_average_override and city not in DEFAULT_MARKET_AVERAGE_SQM:
        risk += 10
        flags.append("R-012 Vergleichsdaten fehlen (Fallback-Durchschnitt verwendet)")

    # Sehr günstige Objekte sind ebenfalls ein Risikosignal (mögliche
    # verschwiegene Mängel, Rechtsprobleme, Zwangsverkauf).
    if sqm_price < market_average * 0.6:
        risk += 20
        flags.append("R-013 Preis auffällig unter Marktdurchschnitt")

    return {
        "risk_points": min(risk, 100),
        "sqm_price": round(sqm_price, 2),
        "market_average": market_average,
        "flags": flags,
    }
