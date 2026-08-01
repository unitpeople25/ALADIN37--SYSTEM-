"""
ALADIN37 Financial Trust Engine - Lombard Engine
v1.2

Berechnet die sofortige Beleihungslinie (LTV) je Asset. Zwei Haircut-Ebenen:
1. Volatilitaets-Haircut (hohe 30T-Vola -> niedrigere Beleihung)
2. Verifikations-Haircut (< BANK_CONFIRMED -> 50% Abschlag, schuetzt vor
   ungeprueften Selbstauskuenften/gefaelschten Uploads)
"""

from decimal import Decimal, ROUND_HALF_UP

from financial_trust.models import Asset, AssetType, VerificationLevel

LTV_MATRIX = {
    AssetType.CASH: Decimal("1.00"),
    AssetType.SOVEREIGN_BONDS: Decimal("0.80"),
    AssetType.INVESTMENT_FUNDS: Decimal("0.60"),
    AssetType.SINGLE_EQUITIES: Decimal("0.40"),
    AssetType.CRYPTO: Decimal("0.20"),
    AssetType.REAL_ESTATE: Decimal("0.00"),  # in V1 nicht kurzfristig liquidierbar
}

VOLATILITY_HAIRCUT_THRESHOLD = 0.25
VOLATILITY_HAIRCUT = Decimal("0.15")
UNVERIFIED_HAIRCUT_FACTOR = Decimal("0.50")


class LombardEngine:

    @classmethod
    def calculate_ltv(cls, asset: Asset) -> Decimal:
        base_ltv = LTV_MATRIX.get(asset.asset_type, Decimal("0.00"))

        if asset.asset_type in (AssetType.INVESTMENT_FUNDS, AssetType.SINGLE_EQUITIES) \
                and asset.volatility_30d > VOLATILITY_HAIRCUT_THRESHOLD:
            base_ltv -= VOLATILITY_HAIRCUT

        if asset.verification_level < VerificationLevel.BANK_CONFIRMED:
            base_ltv *= UNVERIFIED_HAIRCUT_FACTOR

        return max(base_ltv, Decimal("0.00"))

    @classmethod
    def get_lombard_line(cls, asset: Asset) -> Decimal:
        ltv = cls.calculate_ltv(asset)
        return (asset.current_value * ltv).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
