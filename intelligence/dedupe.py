"""
ALADIN37 - Dedupe Intelligence
Phase 5 / Modul 3

Zwei Ebenen:
1. Exakter Hash (aus Phase 4) - schnelle, harte Duplikaterkennung.
2. Property Identity Score - erkennt dasselbe Objekt über mehrere Quellen
   hinweg, auch wenn Preis/Adresse leicht abweichen (Idealista 365k,
   Makler 379k, Fotobook 375k = gleiche Immobilie).
"""

import hashlib
import re

IDENTITY_WEIGHTS = {
    "address": 40,
    "living_area": 20,
    "rooms": 15,
    "price": 15,
    "images": 10,
}

IDENTITY_MATCH_THRESHOLD = 70  # ab hier gilt es als "wahrscheinlich dasselbe Objekt"

PRICE_SIMILARITY_TOLERANCE = 0.05   # 5% Preisabweichung -> volle Punkte
PRICE_SIMILARITY_MAX_TOLERANCE = 0.15  # 15% Abweichung -> 0 Punkte


def generate_hash(property_data: dict) -> str:
    """Exakter Dedupe-Hash wie in Phase 4."""
    values = [
        property_data.get("property_type"),
        property_data.get("address"),
        property_data.get("city"),
        property_data.get("price"),
        property_data.get("rooms"),
        property_data.get("living_area"),
    ]
    raw = "|".join(str(v).lower().strip() for v in values)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_address(address: str) -> str:
    if not address:
        return ""
    address = address.lower().strip()
    address = re.sub(r"[.,]", "", address)
    address = re.sub(r"\s+", " ", address)
    return address


def _address_score(a: str, b: str) -> float:
    a, b = _normalize_address(a), _normalize_address(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Teilübereinstimmung (z.B. "Calle Ramon de Moncada" vs.
    # "Calle Ramon de Moncada 15") - Straße stimmt, Hausnummer fehlt/abweicht.
    if a in b or b in a:
        return 0.75
    a_tokens, b_tokens = set(a.split()), set(b.split())
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens) / len(a_tokens | b_tokens)
    return overlap


def _numeric_exact_score(x, y) -> float:
    if x is None or y is None:
        return 0.0
    return 1.0 if x == y else 0.0


def _price_similarity_score(price_a, price_b) -> float:
    if not price_a or not price_b:
        return 0.0
    diff_ratio = abs(price_a - price_b) / max(price_a, price_b)
    if diff_ratio <= PRICE_SIMILARITY_TOLERANCE:
        return 1.0
    if diff_ratio >= PRICE_SIMILARITY_MAX_TOLERANCE:
        return 0.0
    # linear interpoliert zwischen voller Toleranz und Maximaltoleranz
    span = PRICE_SIMILARITY_MAX_TOLERANCE - PRICE_SIMILARITY_TOLERANCE
    return 1.0 - ((diff_ratio - PRICE_SIMILARITY_TOLERANCE) / span)


def _image_similarity_score(images_a, images_b) -> float:
    """
    Platzhalter-Heuristik: erwartet Listen von Bild-Hashes (z.B. pHash).
    Ohne echte Bilddaten liefert die Funktion 0 - sie ist bewusst so gebaut,
    dass ein späteres pHash/CLIP-Modul nur eingesteckt werden muss.
    """
    if not images_a or not images_b:
        return 0.0
    overlap = len(set(images_a) & set(images_b))
    total = max(len(images_a), len(images_b))
    return overlap / total if total else 0.0


def identity_score(listing_a: dict, listing_b: dict) -> dict:
    """
    Berechnet den Property Identity Score zwischen zwei (normalisierten)
    Listings. Gibt Gesamtscore (0-100) plus Aufschlüsselung zurück.
    """
    address_s = _address_score(listing_a.get("address"), listing_b.get("address"))
    area_s = _numeric_exact_score(listing_a.get("living_area"), listing_b.get("living_area"))
    rooms_s = _numeric_exact_score(listing_a.get("rooms"), listing_b.get("rooms"))
    price_s = _price_similarity_score(listing_a.get("price"), listing_b.get("price"))
    images_s = _image_similarity_score(listing_a.get("images"), listing_b.get("images"))

    breakdown = {
        "address": round(address_s * IDENTITY_WEIGHTS["address"], 1),
        "living_area": round(area_s * IDENTITY_WEIGHTS["living_area"], 1),
        "rooms": round(rooms_s * IDENTITY_WEIGHTS["rooms"], 1),
        "price": round(price_s * IDENTITY_WEIGHTS["price"], 1),
        "images": round(images_s * IDENTITY_WEIGHTS["images"], 1),
    }
    total = round(sum(breakdown.values()), 1)

    return {
        "total": total,
        "is_likely_duplicate": total >= IDENTITY_MATCH_THRESHOLD,
        "breakdown": breakdown,
    }


def find_best_match(candidate: dict, existing_listings: list) -> dict | None:
    """
    existing_listings: Liste von dict-artigen Listing-Objekten (z.B. aus
    ListingRepository.find_candidates()). Gibt das beste Match zurück,
    falls über dem Schwellenwert, sonst None.
    """
    best = None
    for existing in existing_listings:
        result = identity_score(candidate, dict(existing))
        if result["is_likely_duplicate"] and (best is None or result["total"] > best["total"]):
            best = {**result, "listing_id": existing["id"] if "id" in existing.keys() else existing.get("id")}
    return best
