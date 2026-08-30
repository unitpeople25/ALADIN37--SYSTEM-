"""
ALADIN37 - Broker Risk Engine
Phase 5 / Risk-Modul

Heuristik-Start (fehlende Dokumente, Drucksignale im Text). Später:
echte Makler-Historie aus der DB (Reaktionszeit, Widerspruchsrate über
mehrere Listings hinweg, bekannte Druckmuster P-01 bis P-10 aus dem
bestehenden ALADIN37-Framework).

Rückgabe: risk_points (0-100, höher = weniger vertrauenswürdig) + Flags.
"""

import re

REQUIRED_DOCUMENT_FIELDS = ["energy_certificate", "license", "year_built"]

PRESSURE_PATTERNS = [
    r"nur\s+heute", r"letzte\s+chance", r"mehrere\s+interessenten",
    r"solo\s+hoy", r"[uú]ltima\s+oportunidad", r"varios\s+interesados",
    r"today\s+only", r"last\s+chance", r"multiple\s+buyers?\s+interested",
]


def assess(listing: dict, normalized: dict, broker_history: dict = None) -> dict:
    """
    broker_history: optionales dict aus einer zukünftigen
    BrokerRepository-Abfrage, z.B. {"avg_response_hours": 3, "contradiction_rate": 0.1}.
    Wird hier defensiv behandelt, damit das Modul auch ohne Historie läuft.
    """
    risk = 0
    flags = []

    missing_docs = [f for f in REQUIRED_DOCUMENT_FIELDS if not normalized.get(f)]
    if missing_docs:
        risk += min(25, len(missing_docs) * 8)
        flags.append(f"MLC-004 Informationslücken ({', '.join(missing_docs)})")

    raw_text = (listing.get("_raw_text") or normalized.get("_raw_text") or "").lower()
    if any(re.search(p, raw_text, flags=re.IGNORECASE) for p in PRESSURE_PATTERNS):
        risk += 15
        flags.append("P-03 Zeitdruck-/Verknappungssignal im Text")

    if normalized.get("has_rental_license") is False and normalized.get("_source") == "idealista":
        risk += 10
        flags.append("MLC-002 Vermietung ohne erkennbare Lizenz beworben")

    for flag in normalized.get("_normalizer_flags", []):
        if flag == "SEA_VIEW_UNVERIFIED":
            risk += 8
            flags.append("MLC-010 Meerblick behauptet, nicht verifizierbar")
        if flag == "LICENSE_CLAIM_AMBIGUOUS":
            risk += 8
            flags.append("MLC-005 Lizenzstatus unklar formuliert")

    if broker_history:
        if broker_history.get("contradiction_rate", 0) > 0.2:
            risk += 20
            flags.append("P-07 Makler mit hoher historischer Widerspruchsrate")
        if broker_history.get("avg_response_hours", 0) > 48:
            risk += 5
            flags.append("P-08 Träge Reaktionszeit laut Historie")

    return {
        "risk_points": min(risk, 100),
        "flags": flags,
    }
