"""
Demo seed data — gives the app a realistic, populated look for demonstrations.
Covers multiple subjects, varied confidence levels, a 30-day history, and a
5-day clearing streak so the Progress and Reports pages look compelling.
"""
import sqlite3
import uuid
from datetime import datetime, timedelta

from .init_db import DB_PATH

# ---------------------------------------------------------------------------
# (name, subject, status, confidence, days_ago_created, days_ago_cleared)
# days_ago_cleared is None for non-cleared concepts
# ---------------------------------------------------------------------------
DEMO_CONCEPTS = [
    # ── Computer Science ────────────────────────────────────────────────────
    ("Big-O Notation",            "Computer Science", "clear",   0.94, 28, 22),
    ("Recursion",                 "Computer Science", "clear",   0.91, 26, 18),
    ("Binary Search Trees",       "Computer Science", "clear",   0.87, 24, 14),
    ("Dynamic Programming",       "Computer Science", "on-loan", 0.61, 20, None),
    ("Graph Traversal (BFS/DFS)", "Computer Science", "on-loan", 0.47, 16, None),
    ("Hash Tables",               "Computer Science", "persists",0.35, 12, None),

    # ── Calculus ────────────────────────────────────────────────────────────
    ("Limits & Continuity",       "Calculus",         "clear",   0.96, 30, 25),
    ("Derivatives (Chain Rule)",  "Calculus",         "clear",   0.90, 27, 20),
    ("Integration by Parts",      "Calculus",         "clear",   0.85, 22, 15),
    ("Taylor Series",             "Calculus",         "clear",   0.80, 10,  4),  # cleared 4 days ago
    ("Multivariable Gradients",   "Calculus",         "clear",   0.76,  9,  3),  # cleared 3 days ago

    # ── Physics ─────────────────────────────────────────────────────────────
    ("Newton's Laws of Motion",   "Physics",          "clear",   0.92, 29, 23),
    ("Conservation of Energy",    "Physics",          "clear",   0.88, 21, 13),
    ("Wave-Particle Duality",     "Physics",          "clear",   0.78,  9,  2),  # cleared 2 days ago
    ("Quantum Superposition",     "Physics",          "persists",0.28,  7, None),

    # ── Biology ─────────────────────────────────────────────────────────────
    ("DNA Replication",           "Biology",          "clear",   0.93, 25, 19),
    ("Krebs Cycle",               "Biology",          "clear",   0.82, 11,  1),  # cleared yesterday
    ("CRISPR Gene Editing",       "Biology",          "on-loan", 0.44,  6, None),

    # ── Economics ───────────────────────────────────────────────────────────
    ("Supply & Demand Curves",    "Economics",        "clear",   0.89, 23, 17),
    ("Game Theory Basics",        "Economics",        "clear",   0.84,  8,  0),  # cleared today
    ("Monetary Policy",           "Economics",        "persists",0.31,  4, None),
]

# ---------------------------------------------------------------------------
# Sessions — all outcome='cleared' so the streak counter and trend chart work.
# The first 5 entries cover today through 4 days ago → 5-day streak.
# ---------------------------------------------------------------------------
DEMO_SESSIONS = [
    # ── 5-day streak ────────────────────────────────────────────────────────
    ("Game Theory Basics",        0),   # today
    ("Krebs Cycle",               1),   # yesterday
    ("Wave-Particle Duality",     2),
    ("Multivariable Gradients",   3),
    ("Taylor Series",             4),
    # ── earlier history (populates 30-day trend graph) ───────────────────────
    ("Conservation of Energy",   13),
    ("DNA Replication",          19),
    ("Integration by Parts",     15),
    ("Derivatives (Chain Rule)", 20),
    ("Supply & Demand Curves",   17),
    ("Newton's Laws of Motion",  23),
    ("Limits & Continuity",      25),
    ("Binary Search Trees",      14),
    ("Recursion",                18),
    ("Big-O Notation",           22),
]


def seed(student_id: str = "demo", force: bool = False) -> None:
    conn = sqlite3.connect(DB_PATH)

    if force:
        # Wipe existing demo data so the reset button actually resets
        conn.execute("DELETE FROM concepts WHERE student_id=?", [student_id])
        conn.execute("DELETE FROM sessions WHERE student_id=?", [student_id])
        conn.commit()
    else:
        count = conn.execute(
            "SELECT COUNT(*) FROM concepts WHERE student_id=?", [student_id]
        ).fetchone()[0]
        if count > 0:
            conn.close()
            return

    now = datetime.now()

    # ── Insert concepts ──────────────────────────────────────────────────────
    concept_ids: dict[str, str] = {}
    for name, subject, status, conf, days_created, days_cleared in DEMO_CONCEPTS:
        cid = str(uuid.uuid4())
        concept_ids[name] = cid
        created_at = (now - timedelta(days=days_created)).isoformat()
        last_seen  = (now - timedelta(days=max(0, (days_cleared or days_created) - 1))).isoformat()
        cleared_at = (now - timedelta(days=days_cleared)).isoformat() if days_cleared is not None else None
        conn.execute(
            """INSERT INTO concepts
               (id, student_id, name, subject, status, confidence,
                created_at, last_seen, cleared_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [cid, student_id, name, subject, status, conf,
             created_at, last_seen, cleared_at],
        )

    # ── Insert sessions ──────────────────────────────────────────────────────
    # All sessions use outcome='cleared' so the streak counter and trend
    # chart register them correctly (both queries filter on outcome='cleared').
    for concept_name, days_ago in DEMO_SESSIONS:
        ended_at = (now - timedelta(days=days_ago)).replace(
            hour=18, minute=30, second=0, microsecond=0
        ).isoformat()
        concept_id = concept_ids.get(concept_name, "")
        conn.execute(
            """INSERT INTO sessions
               (id, student_id, concept_id, concept_name, outcome, ended_at)
               VALUES (?,?,?,?,'cleared',?)""",
            [str(uuid.uuid4()), student_id, concept_id, concept_name, ended_at],
        )

    conn.commit()
    conn.close()
