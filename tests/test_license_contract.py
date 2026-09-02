from intelligence.normalizer import normalize


def test_normalizer_maps_extracted_license_to_rental_license_flag():
    extracted = {
        "license": "ETV-12345",
        "_raw_text": "Objekt mit ETV-12345",
    }

    normalized = normalize(extracted)

    assert normalized["has_rental_license"] is True


def test_explicit_negative_rental_license_is_not_overwritten():
    extracted = {
        "license": "ETV-12345",
        "has_rental_license": False,
        "_raw_text": "Objekt mit widersprüchlichen Angaben",
    }

    normalized = normalize(extracted)

    assert normalized["has_rental_license"] is False
