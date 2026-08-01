"""
ALADIN37 - Datenmodell
Phase 1 (Core) + Phase 5 (Scoring-Spalten) Erweiterung
"""

from database.connection import get_connection


def _add_column_if_missing(conn, table, column, coltype):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,

        source TEXT,
        external_id TEXT,

        property_type TEXT,
        city TEXT,
        address TEXT,

        price REAL,
        rooms INTEGER,
        living_area REAL,

        dedupe_hash TEXT UNIQUE,

        status TEXT DEFAULT 'new',

        raw_text TEXT,
        extracted_json TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        event_type TEXT,
        payload TEXT,
        FOREIGN KEY(listing_id) REFERENCES listings(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        received_at TEXT DEFAULT CURRENT_TIMESTAMP,
        source TEXT,
        message TEXT,
        processed INTEGER DEFAULT 0,
        error TEXT
    )
    """)

    # --- Phase 5: Intelligence-Layer-Erweiterungen ---
    # Bestehende DBs aus Phase 1-4 bekommen die neuen Spalten per ALTER TABLE
    # nachgerüstet, ohne dass Daten verloren gehen.
    _add_column_if_missing(conn, "listings", "normalized_json", "TEXT")
    _add_column_if_missing(conn, "listings", "location_score", "REAL")
    _add_column_if_missing(conn, "listings", "price_risk_score", "REAL")
    _add_column_if_missing(conn, "listings", "rental_score", "REAL")
    _add_column_if_missing(conn, "listings", "broker_score", "REAL")
    _add_column_if_missing(conn, "listings", "total_score", "REAL")
    _add_column_if_missing(conn, "listings", "decision", "TEXT")
    _add_column_if_missing(conn, "listings", "risk_flags_json", "TEXT")

    conn.commit()
    conn.close()
