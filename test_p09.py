import json
from pipeline import process_inbound
from financial_trust.api.main import app
from fastapi.testclient import TestClient

test_email = """
Hallo, bezüglich Finca Andratx. Da Sie mir keine Unterlagen schicken, kann und will nicht mehr warten. 
Besichtigung nur gegen nicht rückzahlbare Vergütung vorab und Kapitalnachweis!
"""

print("--- 1. INTELLIGENCE PIPELINE RUN ---")
res = process_inbound(
    raw_text=test_email,
    source="email",
    url="mailto:makler@example.com",
    title="Finca Andratx Eskalationstest",
    price=850000.0,
    currency="EUR"
)

client = TestClient(app)
passport_resp = client.post("/api/v1/passport/issue", json={
    "investor_id": "INV-P09-TEST",
    "listing_id": res["listing_id"],
    "verified_equity_eur": 1000000.0,
    "kyc_verified": True
})

print("\n--- 2. ISSUED PASSPORT REASON CODES ---")
print(json.dumps(passport_resp.json()["reason_codes"], indent=2, ensure_ascii=False))
