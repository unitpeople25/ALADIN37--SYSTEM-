"""
ALADIN37 - Normalizer
Phase 5 / Modul 2

Maklersprache -> Standardsprache. Arbeitet auf dem extrahierten JSON
UND zusätzlich direkt auf dem Originaltext, um Signale zu erkennen,
die der Extractor evtl. nicht sauber in ein Feld gepackt hat.
"""

import re

# Phrase -> (Zielfeld, Wert)
PHRASE_MAP = {
    r"vistas?\s+al\s+mar": ("sea_view", True),
    r"sea\s*view": ("sea_view", True),
    r"meerblick": ("sea_view", True),

    r"reformad[oa]": ("condition", "renovated"),
    r"renovated": ("condition", "renovated"),
    r"renoviert": ("condition", "renovated"),

    r"a\s+reformar": ("condition", "needs_renovation"),
    r"necesita\s+reforma": ("condition", "needs_renovation"),
    r"sanierungsbed[üu]rftig": ("condition", "needs_renovation"),

    r"primera\s+l[íi]nea": ("location_class", "frontline"),
    r"first\s*line": ("location_class", "frontline"),
    r"erste\s+meereslinie": ("location_class", "frontline"),

    r"segunda\s+l[íi]nea": ("location_class", "second_line"),

    r"llave\s+en\s+mano": ("condition", "move_in_ready"),

    r"licencia\s+tur[íi]stica|ferienvermietlizenz|holiday\s+rental\s+licen[cs]e": ("has_rental_license", True),

    r"sin\s+licencia|keine\s+lizenz|no\s+license": ("has_rental_license", False),

    r"ascensor|elevator|aufzug": ("has_elevator", True),

    r"orientaci[óo]n\s+sur|south\s+orientation|s[üu]dausrichtung": ("orientation", "south"),
}


def normalize(extracted: dict) -> dict:
    """
    Nimmt das rohe Extraktions-JSON, gibt eine normalisierte Kopie zurück.
    Verändert das Original nicht (extracted bleibt als Beweis-Quelle erhalten).
    """
    normalized = dict(extracted)
    raw_text = (extracted.get("_raw_text") or "").lower()

    signals_found = {}

    for pattern, (field, value) in PHRASE_MAP.items():
        if re.search(pattern, raw_text, flags=re.IGNORECASE):
            signals_found[field] = value

    for field, value in signals_found.items():
        # Text-Signal ergänzt nur, überschreibt aber kein explizit
        # extrahiertes Feld (der Extractor hat i.d.R. mehr Kontext).
        if normalized.get(field) in (None, ""):
            normalized[field] = value

    # Contract: Der Extractor liefert eine konkrete "license", während
    # die Scoring Engine mit dem booleschen Feld "has_rental_license"
    # arbeitet. Eine vorhandene Lizenzangabe ist ein positives Signal,
    # sofern kein expliziter boolescher Wert bereits gesetzt wurde.
    if normalized.get("license") not in (None, ""):
        if normalized.get("has_rental_license") is None:
            normalized["has_rental_license"] = True

    # Widerspruchs-Erkennung: Textbehauptung ohne strukturelles Gegenstück
    # (z.B. "Meerblick" im Text, aber kein Foto-/Lizenz-Beweis im System) -
    # wird als Flag mitgegeben, die Risk Engine wertet es aus.
    normalized["_normalizer_flags"] = _detect_unverified_claims(raw_text, normalized)

    return normalized


def _detect_unverified_claims(raw_text: str, normalized: dict) -> list:
    flags = []

    if normalized.get("sea_view") and "sea_view_verified" not in normalized:
        flags.append("SEA_VIEW_UNVERIFIED")

    if re.search(r"licencia|lizenz|license", raw_text, flags=re.IGNORECASE) and \
            normalized.get("has_rental_license") is None:
        flags.append("LICENSE_CLAIM_AMBIGUOUS")

    return flags
