from intelligence.normalizer import normalize
from intelligence.scoring import score_listing


def test_normalizer_flags_reach_scoring_risk_flags():
    extracted = {
        "city": "Palma",
        "price": 350000,
        "sea_view": True,
        "_raw_text": "Meerblick ohne verifizierten Nachweis",
    }

    normalized = normalize(extracted)

    assert "SEA_VIEW_UNVERIFIED" in normalized["_normalizer_flags"]

    result = score_listing(
        {"price": normalized.get("price"), "_raw_text": extracted["_raw_text"]},
        normalized,
    )

    assert "SEA_VIEW_UNVERIFIED" in result["flags"]
