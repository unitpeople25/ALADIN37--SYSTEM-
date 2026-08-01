"""
ALADIN37 - Inbox Repository
Rohnachrichten (WhatsApp/E-Mail/Idealista) bevor sie verarbeitet werden.
"""

from database.connection import get_connection


class InboxRepository:

    def add(self, source: str, message: str) -> int:
        conn = get_connection()
        cursor = conn.execute("""
        INSERT INTO inbox (source, message) VALUES (?, ?)
        """, (source, message))
        conn.commit()
        inbox_id = cursor.lastrowid
        conn.close()
        return inbox_id

    def mark_processed(self, inbox_id: int, error: str = None):
        conn = get_connection()
        conn.execute("""
        UPDATE inbox SET processed=1, error=? WHERE id=?
        """, (error, inbox_id))
        conn.commit()
        conn.close()

    def unprocessed(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM inbox WHERE processed=0 ORDER BY received_at ASC").fetchall()
        conn.close()
        return rows
