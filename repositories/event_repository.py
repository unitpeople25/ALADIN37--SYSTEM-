"""
ALADIN37 - Event Repository
Historisierung: wann wurde was mit einem Listing gemacht.
"""

import json
from database.connection import get_connection


class EventRepository:

    def add(self, listing_id: int, event_type: str, payload: dict = None):
        conn = get_connection()
        conn.execute("""
        INSERT INTO events (listing_id, event_type, payload)
        VALUES (?, ?, ?)
        """, (
            listing_id,
            event_type,
            json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        ))
        conn.commit()
        conn.close()

    def history(self, listing_id: int):
        conn = get_connection()
        rows = conn.execute("""
        SELECT * FROM events WHERE listing_id=? ORDER BY timestamp ASC
        """, (listing_id,)).fetchall()
        conn.close()
        return rows
