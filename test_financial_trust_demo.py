import json
from fastapi.testclient import TestClient
from financial_trust.api.main import app

client = TestClient(app)

payload = {
    "profile": {
        "investor_id": "INV-2026-014",
        "compliance_status": "VERIFIED",
        "source_of_wealth_level": 3,
        "assets": [
            {"institution": "Fidelity Luxemburg", "asset_type": "INVESTMENT_FUNDS",
             "current_value": 420000, "volatility_30d": 0.19, "verification_level": 2},
            {"institution": "FFB", "asset_type": "SOVEREIGN_BONDS",
             "current_value": 210000, "volatility_30d": 0.04, "verification_level": 2},
            {"institution": "Sparkasse DE", "asset_type": "CASH",
             "current_value": 90000, "volatility_30d": 0.0, "verification_level": 3},
        ],
    },
    "price": 365000,
    "listing_id": 1,
    "ttl_days": 7,
}

print("### FALL A: Investor + gekoppeltes Phase-5-Listing (Santa Ponsa) ###\n")
resp = client.post("/api/v1/passport/issue", json=payload)
print("Status:", resp.status_code)
passport = resp.json()
print(json.dumps(passport, indent=2, ensure_ascii=False))

print("\n### VERIFY: unveraendertes Passport ###")
verify_resp = client.post("/api/v1/passport/verify", json=passport)
print(json.dumps(verify_resp.json(), indent=2, ensure_ascii=False))

print("\n### VERIFY: manipuliertes Passport (financial A -> A+ gefaelscht) ###")
tampered = json.loads(json.dumps(passport))
tampered["trust_vector"]["financial"] = "A+"
verify_tampered = client.post("/api/v1/passport/verify", json=tampered)
print("Status:", verify_tampered.status_code)
print(verify_tampered.json())

print("\n### FALL B: Investor ohne Listing (reine Bonitaetspruefung) ###")
payload_no_listing = dict(payload)
payload_no_listing["listing_id"] = None
resp2 = client.post("/api/v1/passport/issue", json=payload_no_listing)
print(json.dumps(resp2.json()["trust_vector"], indent=2, ensure_ascii=False))
