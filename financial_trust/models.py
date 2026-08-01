"""
ALADIN37 Financial Trust Engine - Domain Models
v1.2

Layer 1+2 der Architektur: Identity & Compliance / Asset Verification.

Bewusst OHNE eigenes PropertyTarget-Modell: die Immobilienseite kommt
nicht aus einem separaten, schwächeren Property-Fit-Platzhalter, sondern
direkt aus der bereits produktiven ALADIN37 Phase-5-Pipeline
(intelligence/scoring.py, repositories/listing_repository.py). Siehe
engines/trust_engine.py fuer die Kopplung.
"""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

Money = Decimal


class ComplianceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


class VerificationLevel(IntEnum):
    SELF_DECLARED = 1
    DOCUMENT_UPLOADED = 2
    BANK_CONFIRMED = 3
    API_VERIFIED = 4
    AUDITED = 5


class AssetType(str, Enum):
    CASH = "CASH"
    SOVEREIGN_BONDS = "SOVEREIGN_BONDS"
    INVESTMENT_FUNDS = "INVESTMENT_FUNDS"
    SINGLE_EQUITIES = "SINGLE_EQUITIES"
    REAL_ESTATE = "REAL_ESTATE"
    CRYPTO = "CRYPTO"


class Asset(BaseModel):
    institution: str = Field(..., description="z.B. 'Fidelity Luxemburg', 'FFB'")
    asset_type: AssetType
    isin: Optional[str] = None
    current_value: Money = Field(ge=0)
    currency: str = "EUR"
    volatility_30d: float = Field(ge=0.0, le=5.0)
    # Kein Boolean mehr (Kritikpunkt aus der Diskussion): granulare Stufe
    # statt "source_verified: bool", damit ein hochgeladenes PDF nicht
    # gleich viel zaehlt wie eine Bankbestaetigung.
    verification_level: VerificationLevel = VerificationLevel.SELF_DECLARED


class InvestorProfile(BaseModel):
    investor_id: str
    compliance_status: ComplianceStatus
    # Herkunftsnachweis-Kette (Source of Wealth) getrennt von der reinen
    # Vermoegens-Existenz - das war der Kernpunkt aus Claudes Kritik am
    # ursprungliches "in Sekunden freigeben"-Konzept: die Herkunft der
    # Mittel ist der eigentliche AML-Zweck, nicht nur ihre Existenz.
    source_of_wealth_level: VerificationLevel = VerificationLevel.SELF_DECLARED
    assets: List[Asset]
    existing_liabilities: Money = Decimal("0.00")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("assets")
    @classmethod
    def must_have_assets(cls, v: List[Asset]) -> List[Asset]:
        if not v:
            raise ValueError("Investor muss mindestens einen Vermoegenswert besitzen.")
        return v

    @property
    def total_wealth(self) -> Decimal:
        return sum((a.current_value for a in self.assets), Decimal("0.00"))
