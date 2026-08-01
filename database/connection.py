"""
ALADIN37 - SQLite Connection Layer
Phase 1 (Core Refactor v1.0)
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "aladin37.db"


def get_connection() -> sqlite3.Connection:
    """
    Returns a configured SQLite connection.
    WAL mode allows concurrent readers, which matters once the
    dashboard / API and the ingestion workers read the same DB.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    return conn
