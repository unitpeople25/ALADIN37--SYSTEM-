"""
ALADIN37 - Intelligence Pipeline (Orchestrator)
Phase 5

    INPUT -> Claude Extractor -> Normalizer -> Dedupe Intelligence
          -> Scoring Engine -> Decision Layer -> WEITERVERFOLGEN/PRÜFEN/ABLEHNEN

Dies ist der zentrale Einstiegspunkt, den ingestion/whatsapp.py,
ingestion/email.py und ingestion/idealista.py (Phase 2) später aufrufen.
"""

from database.models import init_database
from repositories.listing_repository import ListingRepository
from repositories.event_repository import EventRepository
from repositories.inbox_repository import InboxRepository

from intelligence import claude_parser, normalizer, dedupe, scoring

# Entscheidungsgrenzen - bewusst als Konstanten, damit sie ohne Codeänderung
# nachjustiert werden können, sobald echte Ergebnisdaten vorliegen.
DECISION_THRESHOLDS = {
    "WEITERVERFOLGEN": 75,
    "WEITER_PRUEFEN": 45,
    # alles darunter -> ABLEHNEN
}


def decide(total_score: float) -> str:
    if total_score >= DECISION_THRESHOLDS["WEITERVERFOLGEN"]:
        return "WEITERVERFOLGEN"
    if total_score >= DECISION_THRESHOLDS["WEITER_PRUEFEN"]:
        return "WEITER PRÜFEN"
    return "ABLEHNEN"


DECISION_ICON = {
    "WEITERVERFOLGEN": "🟢",
    "WEITER PRÜFEN": "🟡",
    "ABLEHNEN": "🔴",
}


def process_raw_input(raw_input: dict, listing_repo: ListingRepository = None,
                       event_repo: EventRepository = None,
                       inbox_repo: InboxRepository = None) -> dict:
    """
    raw_input: {"source": "idealista"|"whatsapp"|"email"|..., "text": "..."}

    Führt den kompletten Phase-5-Flow aus und persistiert das Ergebnis.
    Gibt ein Ergebnis-dict zurück, das direkt für format_report() genutzt
    werden kann.
    """
    listing_repo = listing_repo or ListingRepository()
    event_repo = event_repo or EventRepository()
    inbox_repo = inbox_repo or InboxRepository()

    inbox_id = inbox_repo.add(raw_input.get("source"), raw_input.get("text"))

    # 1. Claude Extractor
    extracted = claude_parser.extract(raw_input, inbox_repo=inbox_repo, inbox_id=inbox_id)

    # 2. Normalizer
    normalized = normalizer.normalize(extracted)

    # 3. Dedupe Intelligence
    exact_hash = dedupe.generate_hash(normalized)
    existing = listing_repo.find_by_hash(exact_hash)

    if existing:
        event_repo.add(existing["id"], "DUPLICATE_DETECTED_EXACT", {"source": raw_input.get("source")})
        inbox_repo.mark_processed(inbox_id)
        return {"status": "duplicate", "listing_id": existing["id"], "match_type": "exact_hash"}

    candidates = listing_repo.find_candidates(
        city=normalized.get("city"), price=normalized.get("price")
    )
    fuzzy_match = dedupe.find_best_match(normalized, candidates)

    if fuzzy_match:
        event_repo.add(fuzzy_match["listing_id"], "DUPLICATE_DETECTED_FUZZY", fuzzy_match)
        inbox_repo.mark_processed(inbox_id)
        return {"status": "duplicate", "listing_id": fuzzy_match["listing_id"],
                "match_type": "fuzzy", "identity_score": fuzzy_match["total"]}

    # Kein Duplikat -> neues Listing anlegen
    listing_id = listing_repo.create({
        "source": raw_input.get("source"),
        "external_id": normalized.get("external_id"),
        "property_type": normalized.get("property_type"),
        "city": normalized.get("city"),
        "address": normalized.get("address"),
        "price": normalized.get("price"),
        "rooms": normalized.get("rooms"),
        "living_area": normalized.get("living_area"),
        "dedupe_hash": exact_hash,
        "raw_text": raw_input.get("text"),
        "extracted_json": extracted,
    })
    event_repo.add(listing_id, "CLAUDE_EXTRACTION", {"source": raw_input.get("source")})

    # 4. Scoring Engine (+ Risk Engine intern)
    listing_row = {"price": normalized.get("price"), "_raw_text": raw_input.get("text")}
    score_result = scoring.score_listing(listing_row, normalized)
    event_repo.add(listing_id, "CLAUDE_ANALYSIS", {
        "total_score": score_result["total_score"],
        "flags": score_result["flags"],
    })

    # 5. Decision Layer
    decision = decide(score_result["total_score"])
    event_repo.add(listing_id, "DECISION_MADE", {"decision": decision})

    listing_repo.update_intelligence(
        listing_id, normalized, score_result, decision, score_result["flags"]
    )

    inbox_repo.mark_processed(inbox_id)

    return {
        "status": "scored",
        "listing_id": listing_id,
        "normalized": normalized,
        "scores": score_result,
        "decision": decision,
    }


def format_report(result: dict) -> str:
    """Formatiert ein Scoring-Ergebnis wie im ALADIN37-Referenzoutput."""
    if result.get("status") == "duplicate":
        return f"Duplikat erkannt (Listing #{result['listing_id']}, Match: {result['match_type']})"

    n = result["normalized"]
    s = result["scores"]
    decision = result["decision"]
    icon = DECISION_ICON.get(decision, "")

    lines = [
        "================================",
        "ALADIN37 PROPERTY INTELLIGENCE",
        "",
        f"Objekt: {n.get('property_type', '?')} {n.get('city', '')}".strip(),
        f"Preis: {n.get('price'):,.0f} €".replace(",", ".") if n.get("price") else "Preis: unbekannt",
        "================================",
        "",
        f"LOCATION SCORE      {s['location_score']}/100",
        f"PRICE RISK          {s['price_risk_score']}/100",
        f"RENTAL POTENTIAL     {s['rental_score']}/100",
        f"BROKER TRUST         {s['broker_score']}/100",
        "",
        f"FINAL DECISION       {s['total_score']}/100",
        "",
        f"STATUS: {icon} {decision}",
        "",
        "RISKS:",
    ]
    lines += [f"  {flag}" for flag in s["flags"]] if s["flags"] else ["  keine"]
    lines.append("================================")
    return "\n".join(lines)


if __name__ == "__main__":
    init_database()
    print("ALADIN37 Datenbank initialisiert:", "data/aladin37.db")
