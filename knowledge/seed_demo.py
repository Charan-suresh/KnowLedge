import sqlite3
import uuid
from datetime import datetime, timedelta

from .init_db import DB_PATH

DEMO_CONCEPTS = [
    ("Physics Mechanics", "on-loan", 0.41),
    ("AP English 12 Themes", "persists", 0.38),
    ("Chemistry Bonding", "on-loan", 0.55),
    ("Civics & Government", "on-loan", 0.62),
    ("World History Revolutions", "on-loan", 0.70),
    ("Research Capstone Project", "on-loan", 0.48),
    ("Biology Lab Analysis", "clear", 0.88),
    ("Calculus AB Limits", "clear", 0.91),
]


def seed(student_id: str = "demo"):
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute(
        "SELECT COUNT(*) FROM concepts WHERE student_id=?",
        [student_id],
    ).fetchone()[0]
    if count > 0:
        conn.close()
        return

    for i, (name, status, conf) in enumerate(DEMO_CONCEPTS):
        created = (datetime.now() - timedelta(days=14 - i)).isoformat()
        cleared = (datetime.now() - timedelta(days=2)).isoformat() if status == "clear" else None
        conn.execute(
            """INSERT INTO concepts
               (id, student_id, name, status, confidence,
                created_at, last_seen, cleared_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            [str(uuid.uuid4()), student_id, name, status, conf, created, created, cleared],
        )
        if status == "clear":
            conn.execute(
                """INSERT INTO sessions
                   (id, student_id, concept_name, outcome, ended_at)
                   VALUES (?,?,?,'cleared',?)""",
                [str(uuid.uuid4()), student_id, name, cleared],
            )
    conn.commit()
    conn.close()
