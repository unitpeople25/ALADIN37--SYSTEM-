"""
ALADIN37 Financial Trust Engine - Core Evaluation
v1.2

Der entscheidende Architekturunterschied zur Copilot-Version: property_fit
wird NICHT als eigene, schwaechere Zwei-Zeilen-Heuristik neu erfunden.
Stattdessen wird das Listing, das die Phase-5-Pipeline (pipeline.py,
intelligence/scoring.py) bereits bewertet hat, direkt herangezogen -
inklusive der echten Risk-Flags (P-xx/MLC-xx/R-xx).

Ergebnis: financial x compliance x property (Phase 5) in einem
gemeinsamen Trust Vector, ohne Property-Risiko-Logik zu duplizieren.

Wichtig (Haftungsprinzip aus der Diskussion): Die Engine liefert eine
Einschaetzung ("basierend auf verifizierten Daten ergibt sich folgende
Risikoeinschaetzung"), nie eine Garantie, und ersetzt keine notarielle
AML-Pruefung (Ley 10/2010 / EU-Geldwaescherichtlinie).
"""

from decimal import Decimal
from typing import Optional

from financial_trust.models import InvestorProfile, AssetType, VerificationLevel, ComplianceStatus
from financial_trust.engines.lombard_engine import LombardEngine

DISCLAIMER = (
    "ADVISORY ONLY. Kein rechtsverbindlicher Proof of Funds, kein Ersatz fuer "
    "die notarielle AML-Pruefung nach spanischem Recht (Ley 10/2010) bzw. "
    "der EU-Geldwaescherichtlinie. Automatisierte Risikoanalyse, keine Garantie."
)


class AladinTrustEngine:

    @classmethod
    def _financial_capability(cls, profile: InvestorProfile, price: Decimal) -> dict:
        cash = sum(
            (a.current_value for a in profile.assets if a.asset_type == AssetType.CASH),
            Decimal("0.00"),
        )
        lombard = sum(
            (LombardEngine.get_lombard_line(a) for a in profile.assets if a.asset_type != AssetType.CASH),
            Decimal("0.00"),
        )
        liquidity_pool = cash + lombard

        total_wealth = profile.total_wealth
        concentration = (price / total_wealth) if total_wealth > 0 else Decimal("1.00")

        if liquidity_pool >= price:
            settlement_status = "READY"
            settlement_days = 3 if cash >= price else 7
        elif liquidity_pool >= price * Decimal("0.5"):
            settlement_status = "PARTIAL"
            settlement_days = 14
        else:
            settlement_status = "INSUFFICIENT_LIQUIDITY"
            settlement_days = None

        if concentration > Decimal("1.00"):
            rating = "C"
        elif concentration > Decimal("0.80"):
            rating = "B-"
        elif settlement_status == "READY" and concentration < Decimal("0.40"):
            rating = "A+"
        elif settlement_status == "READY":
            rating = "A"
        elif settlement_status == "PARTIAL":
            rating = "B"
        else:
            rating = "C"

        return {
            "rating": rating,
            "settlement_status": settlement_status,
            "settlement_time_days": settlement_days,
            "concentration_risk_index": float(round(concentration, 2)),
            "liquidity_pool_eur": float(liquidity_pool),
        }

    @classmethod
    def _compliance_readiness(cls, profile: InvestorProfile) -> str:
        assets_documented = all(
            a.verification_level >= VerificationLevel.DOCUMENT_UPLOADED for a in profile.assets
        )

        if profile.compliance_status == ComplianceStatus.REJECTED:
            return "REJECTED"

        if (profile.compliance_status == ComplianceStatus.VERIFIED
                and profile.source_of_wealth_level >= VerificationLevel.BANK_CONFIRMED
                and assets_documented):
            return "HIGH_READINESS"

        if profile.source_of_wealth_level >= VerificationLevel.DOCUMENT_UPLOADED and assets_documented:
            return "MEDIUM_READINESS"

        return "LOW_READINESS"

    @classmethod
    def _property_context(cls, listing_row: Optional[dict]) -> dict:
        """
        listing_row: ein Row/Dict aus ListingRepository, wie es die Phase-5-
        Pipeline bereits produziert hat (total_score, decision, risk_flags_json).
        Wenn kein Listing uebergeben wird (z.B. reine Bonitaetspruefung ohne
        konkretes Objekt), liefert die Funktion einen neutralen Platzhalter -
        NICHT eine erfundene Bewertung.
        """
        import json

        if listing_row is None:
            return {
                "property_fit": "NOT_ASSESSED",
                "property_score": None,
                "property_decision": None,
                "property_flags": [],
            }

        total_score = listing_row["total_score"] if "total_score" in listing_row.keys() else None
        decision = listing_row["decision"] if "decision" in listing_row.keys() else None
        flags_raw = listing_row["risk_flags_json"] if "risk_flags_json" in listing_row.keys() else None
        flags = json.loads(flags_raw) if flags_raw else []

        # property_fit leitet sich aus der ECHTEN Phase-5-Entscheidung ab,
        # nicht aus einer neuen, unabhaengigen Heuristik.
        fit_map = {
            "WEITERVERFOLGEN": "GOOD",
            "WEITER PRÜFEN": "REVIEW_REQUIRED",
            "ABLEHNEN": "NOT_RECOMMENDED",
        }
        property_fit = fit_map.get(decision, "NOT_ASSESSED")

        return {
            "property_fit": property_fit,
            "property_score": total_score,
            "property_decision": decision,
            "property_flags": flags,
        }

    @classmethod
    def evaluate(cls, profile: InvestorProfile, price: Decimal, listing_row: Optional[dict] = None) -> dict:
        if profile.total_wealth <= 0:
            raise ValueError("Gesamtvermoegen ist 0 - keine Bewertung moeglich.")

        financial = cls._financial_capability(profile, price)
        compliance = cls._compliance_readiness(profile)
        property_ctx = cls._property_context(listing_row)

        reason_codes = []
        if financial["settlement_status"] == "READY":
            reason_codes.append("SUFFICIENT_LIQUIDITY")
        if financial["concentration_risk_index"] < 0.5:
            reason_codes.append("LOW_CONCENTRATION_RISK")
        elif financial["concentration_risk_index"] > 0.8:
            reason_codes.append("HIGH_CONCENTRATION_RISK")
        if compliance in ("HIGH_READINESS", "MEDIUM_READINESS"):
            reason_codes.append("COMPLIANCE_PREPARED")
        elif compliance == "LOW_READINESS":
            reason_codes.append("COMPLIANCE_DOCUMENTATION_INCOMPLETE")
        reason_codes.extend(property_ctx["property_flags"])

        return {
            "trust_vector": {
                "financial": financial["rating"],
                "compliance": compliance,
                "property": property_ctx["property_fit"],
            },
            "settlement_status": financial["settlement_status"],
            "settlement_time_days": financial["settlement_time_days"],
            "concentration_risk_index": financial["concentration_risk_index"],
            "liquidity_pool_eur": financial["liquidity_pool_eur"],
            "property_score": property_ctx["property_score"],
            "property_decision": property_ctx["property_decision"],
            "reason_codes": reason_codes,
            "disclaimer": DISCLAIMER,
        }
