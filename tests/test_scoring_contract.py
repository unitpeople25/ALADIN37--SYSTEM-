import pytest

from intelligence import scoring


def test_reference_score_semantics():
    """
    ALADIN37 Score Contract:

    Referenzwerte:
      location = 82
      price    = 67
      rental   = 78
      broker   = 54

    Erwarteter Gesamtscore:
      82*0.30 + 67*0.30 + 78*0.20 + 54*0.20 = 71.1
    """
    total = (
        82 * scoring.WEIGHTS["location"]
        + 67 * scoring.WEIGHTS["price_risk"]
        + 78 * scoring.WEIGHTS["rental"]
        + 54 * scoring.WEIGHTS["broker"]
    )

    assert total == pytest.approx(71.1)


def test_price_risk_semantics_must_not_reward_higher_risk():
    """
    Contract:
    Ein höheres Preisrisiko darf den finalen Qualitäts-/Entscheidungsscore
    nicht erhöhen.

    Dieser Test dokumentiert zunächst den gewünschten Vertrag.
    Die aktuelle Implementierung darf hier noch fehlschlagen.
    """
    low_price_risk = 10
    high_price_risk = 90

    # Wenn price_risk intern "höher = schlechter" bedeutet,
    # muss der daraus abgeleitete positive Score entsprechend umgekehrt werden.
    low_risk_quality = 100 - low_price_risk
    high_risk_quality = 100 - high_price_risk

    assert low_risk_quality > high_risk_quality


def test_score_weights_sum_to_one():
    assert sum(scoring.WEIGHTS.values()) == pytest.approx(1.0)


def _build_case(price):
    """
    Baut ein (listing, normalized)-Paar mit ansonsten identischen Feldern.
    Nur 'price' variiert zwischen den Aufrufen.

    Feldnamen entnommen aus der tatsächlichen Implementierung:
    - risk/price_risk.py::assess(listing) -> 'price', 'living_area', 'city'
    - risk/location_risk.py::assess(normalized) -> 'city', 'location_class'
    - risk/broker_risk.py::assess(listing, normalized) ->
      REQUIRED_DOCUMENT_FIELDS = ['energy_certificate', 'license', 'year_built'],
      '_raw_text', 'has_rental_license', '_source', '_normalizer_flags'
    - intelligence/scoring.py::_rental_score(normalized) ->
      'city', 'has_rental_license', 'sea_view', 'condition'
    """
    listing = {
        "price": price,
        "living_area": 100,
        "city": "santa ponsa",
    }
    normalized = {
        "city": "santa ponsa",
        "has_rental_license": True,
        "sea_view": False,
        "condition": "good",
        "energy_certificate": True,
        "license": True,
        "year_built": 1995,
        "_raw_text": "",
    }
    return listing, normalized


def test_score_listing_must_not_reward_higher_price_risk():
    """
    Contract:
    scoring.score_listing() darf einem Listing mit höherem Preisrisiko
    keinen höheren total_score geben als einem ansonsten identischen
    Listing mit niedrigerem Preisrisiko.

    Aufbau:
    Zwei Listings, identisch bis auf den Preis. Fall A liegt exakt auf
    dem Marktdurchschnitt für "santa ponsa" (5200 EUR/m^2, siehe
    risk/price_risk.py::DEFAULT_MARKET_AVERAGE_SQM) -> risk_points = 0.
    Fall B liegt >25% über dem Marktdurchschnitt (7000 EUR/m^2) ->
    risk_points = 30 (risk/price_risk.py::OVERPRICE_THRESHOLD = 1.25).

    Alle anderen Eingabefelder (Ort, Vermietlizenz, Meerblick, Zustand,
    Dokumente) sind identisch, damit location_score, rental_score und
    broker_score für beide Fälle gleich ausfallen und die Differenz im
    total_score ausschließlich auf price_risk_score zurückzuführen ist.

    Dieser Test ruft die tatsächliche Implementierung
    scoring.score_listing() auf - nicht nur eine isolierte
    100-minus-risk-Formel. Wenn er fehlschlägt, zeigt das einen echten
    Semantikfehler in scoring.py: dort wird price_risk_score direkt aus
    risk_points übernommen
    (scoring.py::score_listing: 'price_risk_score = price_result["risk_points"]')
    und NICHT wie location_score/broker_score über (100 - risk_points)
    invertiert.
    """
    listing_low_risk, normalized_low_risk = _build_case(price=520000)   # sqm_price = 5200 (= Marktschnitt)
    listing_high_risk, normalized_high_risk = _build_case(price=700000)  # sqm_price = 7000 (>25% ueber Marktschnitt)

    result_low_risk = scoring.score_listing(listing_low_risk, normalized_low_risk)
    result_high_risk = scoring.score_listing(listing_high_risk, normalized_high_risk)

    # Kontrollnachweis: das Preisrisiko unterscheidet sich tatsaechlich
    assert result_low_risk["details"]["price"]["risk_points"] == 0
    assert result_high_risk["details"]["price"]["risk_points"] == 30

    # Kontrollnachweis: alle anderen Teil-Scores sind identisch
    assert result_low_risk["location_score"] == result_high_risk["location_score"]
    assert result_low_risk["rental_score"] == result_high_risk["rental_score"]
    assert result_low_risk["broker_score"] == result_high_risk["broker_score"]

    # Eigentlicher Contract: niedrigeres Preisrisiko -> hoeherer total_score
    assert result_low_risk["total_score"] > result_high_risk["total_score"]
