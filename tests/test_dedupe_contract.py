from intelligence.dedupe import (
    PRICE_SIMILARITY_MAX_TOLERANCE,
    identity_score,
)
from repositories.listing_repository import ListingRepository


def test_dedupe_price_contract_allows_candidates_up_to_max_tolerance():
    """
    The Dedupe Intelligence layer explicitly supports price differences
    up to PRICE_SIMILARITY_MAX_TOLERANCE.

    This test verifies that a 12% price difference is still inside
    the Dedupe engine's supported range and can produce a duplicate match.
    """
    assert PRICE_SIMILARITY_MAX_TOLERANCE == 0.15

    base_price = 365_000
    candidate_price = base_price * 1.12

    price_difference = abs(candidate_price - base_price) / base_price

    assert price_difference < PRICE_SIMILARITY_MAX_TOLERANCE

    result = identity_score(
        {
            "address": "Example Street 1",
            "living_area": 100,
            "rooms": 4,
            "price": base_price,
            "images": [],
        },
        {
            "address": "Example Street 1",
            "living_area": 100,
            "rooms": 4,
            "price": candidate_price,
            "images": [],
        },
    )

    assert result["is_likely_duplicate"] is True


def test_repository_prefilter_does_not_narrow_dedupe_contract():
    """
    The repository prefilter is the gate before Dedupe Intelligence.

    Its default tolerance must be at least as wide as the Dedupe engine's
    maximum supported price similarity tolerance.
    """
    default_tolerance = ListingRepository.find_candidates.__defaults__[-1]

    assert default_tolerance >= PRICE_SIMILARITY_MAX_TOLERANCE, (
        "Repository candidate prefilter is narrower than the Dedupe "
        "price-similarity contract: "
        f"{default_tolerance:.0%} < "
        f"{PRICE_SIMILARITY_MAX_TOLERANCE:.0%}"
    )
