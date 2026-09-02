"""
ALADIN37 - Listing Repository
Phase 4 (Repository Layer) + Phase 5 (Scoring-Persistenz, Fuzzy-Kandidatensuche)
"""

import json
from database.connection import get_connection
from intelligence.dedupe import PRICE_SIMILARITY_MAX_TOLERANCE


class ListingRepository:

    def create(self, data: dict) -> int:
        conn = get_connection()

        cursor = conn.execute("""
        INSERT INTO listings
        (source, external_id, property_type, city, address, price, rooms,
         living_area, dedupe_hash, raw_text, extracted_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("source"),
            data.get("external_id"),
            data.get("property_type"),
            data.get("city"),
            data.get("address"),
            data.get("price"),
            data.get("rooms"),
            data.get("living_area"),
            data.get("dedupe_hash"),
            data.get("raw_text"),
            json.dumps(data.get("extracted_json"), ensure_ascii=False) if data.get("extracted_json") else None,
        ))

        conn.commit()
        listing_id = cursor.lastrowid
        conn.close()
        return listing_id

    def find_by_hash(self, hash_value: str):
        conn = get_connection()
        result = conn.execute(
            "SELECT * FROM listings WHERE dedupe_hash=?", (hash_value,)
        ).fetchone()
        conn.close()
        return result

    def find_candidates(self, city: str = None, price: float = None, price_tolerance: float = PRICE_SIMILARITY_MAX_TOLERANCE):
        """
        Grobe Vorauswahl möglicher Duplikate für die Identity-Score-Prüfung
        (Phase 5), damit wir nicht die gesamte Tabelle fuzzy vergleichen müssen.
        """
        conn = get_connection()

        query = "SELECT * FROM listings WHERE 1=1"
        params = []

        if city:
            query += " AND lower(city) = lower(?)"
            params.append(city)

        if price:
            low = price * (1 - price_tolerance)
            high = price * (1 + price_tolerance)
            query += " AND price BETWEEN ? AND ?"
            params += [low, high]

        query += " ORDER BY created_at DESC LIMIT 200"

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return rows

    def all(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM listings ORDER BY created_at DESC").fetchall()
        conn.close()
        return rows

    def get(self, listing_id: int):
        conn = get_connection()
        row = conn.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
        conn.close()
        return row

    def update_intelligence(self, listing_id: int, normalized: dict, scores: dict,
                             decision: str, risk_flags: list):
        """
        Persistiert das Ergebnis von Normalizer + Scoring Engine + Risk Engine +
        Decision Layer (Phase 5) am Listing.
        """
        conn = get_connection()
        conn.execute("""
        UPDATE listings SET
            normalized_json = ?,
            location_score = ?,
            price_risk_score = ?,
            rental_score = ?,
            broker_score = ?,
            total_score = ?,
            decision = ?,
            risk_flags_json = ?,
            status = ?
        WHERE id = ?
        """, (
            json.dumps(normalized, ensure_ascii=False),
            scores.get("location_score"),
            scores.get("price_risk_score"),
            scores.get("rental_score"),
            scores.get("broker_score"),
            scores.get("total_score"),
            decision,
            json.dumps(risk_flags, ensure_ascii=False),
            "scored",
            listing_id,
        ))
        conn.commit()
        conn.close()
