import os
import sqlite3

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "knowledge.db",
)


def init():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS concepts (
            id         TEXT PRIMARY KEY,
            student_id TEXT NOT NULL DEFAULT 'default',
            name       TEXT NOT NULL,
            subject    TEXT,
            status     TEXT NOT NULL DEFAULT 'on-loan',
            confidence REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now')),
            last_seen  TEXT DEFAULT (datetime('now')),
            cleared_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id           TEXT PRIMARY KEY,
            student_id   TEXT NOT NULL DEFAULT 'default',
            concept_id   TEXT,
            concept_name TEXT,
            outcome      TEXT,
            ended_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id         TEXT PRIMARY KEY,
            student_id TEXT,
            event_type TEXT,
            payload    TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )

    existing = [row[1] for row in cursor.execute("PRAGMA table_info(concepts)").fetchall()]
    for col, definition in [
        ("subject", "TEXT"),
        ("cleared_at", "TEXT"),
        ("confidence", "REAL DEFAULT 0.0"),
    ]:
        if col not in existing:
            cursor.execute(f"ALTER TABLE concepts ADD COLUMN {col} {definition}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init()
    print("Database ready.")
