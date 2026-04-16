import sqlite3
from typing import List, Dict, Any, Optional

DB_NAME = "debt_log.db"

VALID_STATUSES = {"borrowed", "clearing", "cleared"}


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
    """Return rows as dictionaries."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_connection() -> sqlite3.Connection:
    """Returns a new DB connection with dict_factory and enabled foreign keys."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Creates database, required tables, and indexes if they don't exist."""
    try:
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS debt_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept TEXT NOT NULL,
                    source_content TEXT,
                    confidence_score REAL,
                    status TEXT DEFAULT 'borrowed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cleared_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clearing_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    debt_id INTEGER,
                    transcript TEXT,
                    session_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (debt_id) REFERENCES debt_entries(id) ON DELETE CASCADE
                )
            """)
            # Index for frequent status-based queries (dashboard + clearing agent)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_debt_status ON debt_entries(status)
            """)
    except sqlite3.Error as e:
        raise RuntimeError(f"Database initialization error: {e}") from e


def add_debt(concept: str, source_content: str, confidence_score: float) -> int:
    """
    Inserts a new debt entry and returns its ID.
    Raises RuntimeError on failure so callers cannot silently ignore it.
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO debt_entries (concept, source_content, confidence_score)
                VALUES (?, ?, ?)
            """, (concept, source_content, confidence_score))
            return cursor.lastrowid
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to add debt entry: {e}") from e


def get_all_debts(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves all debt entries, optionally filtered by status.
    Pass status='borrowed' | 'clearing' | 'cleared' to filter.
    """
    if status and status not in VALID_STATUSES:
        raise ValueError(f"Invalid status filter: '{status}'. Must be one of {VALID_STATUSES}")
    try:
        with get_connection() as conn:
            if status:
                return conn.execute(
                    "SELECT * FROM debt_entries WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                ).fetchall()
            return conn.execute(
                "SELECT * FROM debt_entries ORDER BY created_at DESC"
            ).fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching debts: {e}")
        return []


def get_debt_by_id(debt_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves one debt entry by ID."""
    try:
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM debt_entries WHERE id = ?", (debt_id,)
            ).fetchone()
    except sqlite3.Error as e:
        print(f"Error fetching debt {debt_id}: {e}")
        return None


def get_debt_with_sessions(debt_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves a debt entry with all its clearing sessions attached.
    Used by the Week 3 Socratic agent to get full context in one call.
    Returns None if the debt entry doesn't exist.
    """
    debt = get_debt_by_id(debt_id)
    if debt:
        debt["sessions"] = get_sessions_for_debt(debt_id)
    return debt


def update_debt_status(debt_id: int, status: str):
    """
    Updates status to 'borrowed', 'clearing', or 'cleared'.
    Sets cleared_at timestamp when status is 'cleared', nulls it otherwise.
    Raises ValueError for invalid status strings.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: '{status}'. Must be one of {VALID_STATUSES}")
    try:
        with get_connection() as conn:
            if status == "cleared":
                conn.execute("""
                    UPDATE debt_entries
                    SET status = ?, cleared_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, debt_id))
            else:
                conn.execute("""
                    UPDATE debt_entries
                    SET status = ?, cleared_at = NULL
                    WHERE id = ?
                """, (status, debt_id))
    except sqlite3.Error as e:
        print(f"Error updating status for debt {debt_id}: {e}")


def add_clearing_session(debt_id: int, transcript: str):
    """Stores a Socratic session transcript for a given debt entry."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO clearing_sessions (debt_id, transcript) VALUES (?, ?)
            """, (debt_id, transcript))
    except sqlite3.Error as e:
        print(f"Error adding clearing session for debt {debt_id}: {e}")


def get_sessions_for_debt(debt_id: int) -> List[Dict[str, Any]]:
    """Retrieves all clearing sessions for a debt entry, oldest first."""
    try:
        with get_connection() as conn:
            return conn.execute("""
                SELECT * FROM clearing_sessions
                WHERE debt_id = ?
                ORDER BY session_at ASC
            """, (debt_id,)).fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching sessions for debt {debt_id}: {e}")
        return []
   