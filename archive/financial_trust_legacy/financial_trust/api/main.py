"""
ALADIN37 Financial Trust Engine - API
v1.2

Der zentrale Unterschied zur vorherigen Version: /passport/issue nimmt
optional eine listing_id entgegen. Wenn vorhanden, wird das Ergebnis der
bereits gelaufenen Phase-5-Pipeline (siehe ../pipeline.py) direkt in den
Trust Vector eingespeist - keine zweite, schwaechere Property-Bewertung.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
import uuid

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from financial_trust.models import InvestorProfile
from financial_trust.engines.trust_engine import AladinTrustEngine
from financial_trust.security.signing import AladinSigner

from repositories.listing_repository import ListingRepository

app = FastAPI(
    title="ALADIN37 Financial Trust Engine",
    version="1.2.0",
    description="Digital Buyer Qualification, gekoppelt an die ALADIN37 Property Intelligence Pipeline (Phase 5)",
)

listing_repo = ListingRepository()


class PassportIssueRequest(BaseModel):
    profile: InvestorProfile
    price: Decimal = Field(..., description="Kaufpreis des Zielobjekts")
    listing_id: Optional[int] = Field(
        default=None,
        description="Optional: ID eines bereits durch die Phase-5-Pipeline gescorten Listings. "
                    "Ohne listing_id wird nur die Investoren-Bonitaet bewertet (property=NOT_ASSESSED).",
    )
    ttl_days: int = Field(default=7, ge=1, le=30)


class BrokerPassportView(BaseModel):
    passport_id: str
    issued_at: str
    expires_at: str
    listing_id: Optional[int]
    trust_vector: dict
    settlement_status: str
    settlement_time_days: Optional[int]
    reason_codes: list[str]
    disclaimer: str
    signature_layer: dict


@app.post("/api/v1/passport/issue", response_model=BrokerPassportView, status_code=status.HTTP_201_CREATED)
async def issue_passport(payload: PassportIssueRequest):
    listing_row = None
    if payload.listing_id is not None:
        listing_row = listing_repo.get(payload.listing_id)
        if listing_row is None:
            raise HTTPException(status_code=404, detail=f"Listing #{payload.listing_id} nicht gefunden.")

    try:
        result = AladinTrustEngine.evaluate(payload.profile, payload.price, listing_row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=payload.ttl_days)
    passport_id = f"ALADIN37-{payload.profile.investor_id}-{uuid.uuid4().hex[:8].upper()}"

    signable_core = {
        "passport_id": passport_id,
        "listing_id": payload.listing_id,
        "trust_vector": result["trust_vector"],
        "settlement_status": result["settlement_status"],
        "reason_codes": result["reason_codes"],
    }
    signature = AladinSigner.sign(signable_core)

    return BrokerPassportView(
        passport_id=passport_id,
        issued_at=now.isoformat(),
        expires_at=expires.isoformat(),
        listing_id=payload.listing_id,
        trust_vector=result["trust_vector"],
        settlement_status=result["settlement_status"],
        settlement_time_days=result["settlement_time_days"],
        reason_codes=result["reason_codes"],
        disclaimer=result["disclaimer"],
        signature_layer={
            "algorithm": "Ed25519",
            "public_key": AladinSigner.get_public_key_hex(),
            "signature": signature,
        },
    )


@app.post("/api/v1/passport/verify")
async def verify_passport(passport: dict):
    sig_layer = passport.get("signature_layer", {})
    if sig_layer.get("algorithm") != "Ed25519":
        raise HTTPException(status_code=400, detail="Unbekannter oder fehlender Signatur-Algorithmus.")

    signable_core = {
        "passport_id": passport.get("passport_id"),
        "listing_id": passport.get("listing_id"),
        "trust_vector": passport.get("trust_vector"),
        "settlement_status": passport.get("settlement_status"),
        "reason_codes": passport.get("reason_codes"),
    }

    is_valid = AladinSigner.verify(signable_core, sig_layer.get("signature", ""), sig_layer.get("public_key", ""))

    if not is_valid:
        raise HTTPException(status_code=400, detail="Signatur ungueltig - Passport wurde manipuliert oder ist gefaelscht.")

    expires_at = datetime.fromisoformat(passport["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        return {"status": "EXPIRED", "detail": f"Passport ist am {passport['expires_at']} abgelaufen."}

    return {"status": "VERIFIED", "message": "Signatur und Integritaet bestaetigt."}
