"""
Demo/Test: verifiziert den kompletten Phase-5-Flow ohne echten API-Call.
Mockt intelligence.claude_parser.extract() mit einer festen Extraktion,
testet dann Normalizer -> Dedupe -> Scoring -> Decision -> Report.
"""

import sys
from unittest.mock import patch

sys.path.insert(0, ".")

from database.models import init_database
from repositories.listing_repository import ListingRepository
from repositories.event_repository import EventRepository
from repositories.inbox_repository import InboxRepository
import pipeline


MOCK_EXTRACTIONS = {
    "idealista_ramon_de_moncada": {
        "property_type": "Apartment",
        "city": "Santa Ponsa",
        "address": "Calle Ramon de Moncada 15",
        "price": 365000,
        "rooms": 1,
        "bathrooms": 1,
        "living_area": 50,
        "terrace": True,
        "sea_view": True,
        "year_built": None,
        "energy_certificate": None,
        "license": None,
        "features": ["renovated", "elevator", "south orientation"],
        "_source": "idealista",
        "_raw_text": (
            "Fantastico apartamento en Santa Ponsa, vistas al mar, "
            "reformado, ascensor, orientacion sur. Solo hoy, varios "
            "interesados. Calle Ramon de Moncada 15."
        ),
    },
    "makler_mail_leicht_abweichend": {
        "property_type": "Apartment",
        "city": "Santa Ponsa",
        "address": "Calle Ramon de Moncada",
        "price": 379000,
        "rooms": 1,
        "bathrooms": 1,
        "living_area": 50,
        "terrace": True,
        "sea_view": True,
        "year_built": None,
        "energy_certificate": None,
        "license": None,
        "features": [],
        "_source": "email",
        "_raw_text": "Schoenes Apartment mit Meerblick, Calle Ramon de Moncada, Santa Ponsa.",
    },
}


def run():
    init_database()
    listing_repo = ListingRepository()
    event_repo = EventRepository()
    inbox_repo = InboxRepository()

    print("### FALL 1: Idealista-Inserat (neues Objekt) ###\n")
    with patch.object(pipeline.claude_parser, "extract",
                       return_value=MOCK_EXTRACTIONS["idealista_ramon_de_moncada"]):
        result_1 = pipeline.process_raw_input(
            {"source": "idealista", "text": MOCK_EXTRACTIONS["idealista_ramon_de_moncada"]["_raw_text"]},
            listing_repo, event_repo, inbox_repo,
        )
    print(pipeline.format_report(result_1))

    print("\n\n### FALL 2: Makler-E-Mail, gleiche Immobilie, abweichender Preis (Fuzzy-Dedupe-Test) ###\n")
    with patch.object(pipeline.claude_parser, "extract",
                       return_value=MOCK_EXTRACTIONS["makler_mail_leicht_abweichend"]):
        result_2 = pipeline.process_raw_input(
            {"source": "email", "text": MOCK_EXTRACTIONS["makler_mail_leicht_abweichend"]["_raw_text"]},
            listing_repo, event_repo, inbox_repo,
        )
    print(pipeline.format_report(result_2))

    print("\n\n### EVENT-HISTORIE Objekt #1 ###\n")
    if result_1.get("listing_id"):
        for e in event_repo.history(result_1["listing_id"]):
            print(f"{e['timestamp']}  {e['event_type']}")


if __name__ == "__main__":
    run()
