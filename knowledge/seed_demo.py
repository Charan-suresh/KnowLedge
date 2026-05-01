"""
Demo seed data — gives the app a realistic, populated look for demonstrations.
Covers multiple subjects, varied confidence levels, a 30-day history, and a
5-day clearing streak so the Progress and Reports pages look compelling.
"""
import sqlite3
import uuid
from datetime import datetime, date, timedelta

from .init_db import DB_PATH

# ---------------------------------------------------------------------------
# (name, subject, status, confidence, days_ago_created, days_ago_cleared)
# days_ago_cleared is None for non-cleared concepts
# ---------------------------------------------------------------------------
DEMO_CONCEPTS = [
    # ── Computer Science ────────────────────────────────────────────────────
    ("Big-O Notation",           "Computer Science", "clear",   0.94, 28, 22),
    ("Recursion",                "Computer Science", "clear",   0.91, 26, 18),
    ("Binary Search Trees",      "Computer Science", "clear",   0.87, 24, 14),
    ("Dynamic Programming",      "Computer Science", "on-loan", 0.61, 20, None),
    ("Graph Traversal (BFS/DFS)","Computer Science", "on-loan", 0.47, 16, None),
    ("Hash Tables",              "Computer Science", "persists",0.35, 12, None),

    # ── Calculus ────────────────────────────────────────────────────────────
    ("Limits & Continuity",      "Calculus",         "clear",   0.96, 30, 25),
    ("Derivatives (Chain Rule)", "Calculus",         "clear",   0.90, 27, 20),
    ("Integration by Parts",     "Calculus",         "clear",   0.85, 22, 15),
    ("Taylor Series",            "Calculus",         "on-loan", 0.58, 10, None),
    ("Multivariable Gradients",  "Calculus",         "on-loan", 0.42, 5,  None),

    # ── Physics ─────────────────────────────────────────────────────────────
    ("Newton's Laws of Motion",  "Physics",          "clear",   0.92, 29, 23),
    ("Conservation of Energy",   "Physics",          "clear",   0.88, 21, 13),
    ("Wave-Particle Duality",    "Physics",          "on-loan", 0.55, 9,  None),
    ("Quantum Superposition",    "Physics",          "persists",0.28, 7,  None),

    # ── Biology ─────────────────────────────────────────────────────────────
    ("DNA Replication",          "Biology",          "clear",   0.93, 25, 19),
    ("Krebs Cycle",              "Biology",          "on-loan", 0.52, 11, None),
    ("CRISPR Gene Editing",      "Biology",          "on-loan", 0.44, 6,  None),

    # ── Economics ───────────────────────────────────────────────────────────
    ("Supply & Demand Curves",   "Economics",        "clear",   0.89, 23, 17),
    ("Game Theory Basics",       "Economics",        "on-loan", 0.63, 8,  None),
    ("Monetary Policy",          "Economics",        "persists",0.31, 4,  None),
]

# Sessions seeded to build a 5-day streak (today through 4 days ago)
# plus scattered clears further back to populate the 30-day history graph.
# Each entry: (concept_name, days_ago_cleared)
DEMO_SESSIONS = [
    # 5-day streak (most recent first)
    ("Multivariable Gradients",  0),   # today — still on-loan, simulate a partial attempt
    ("Taylor Series",            1),
    ("Graph Traversal (BFS/DFS)",2),
    ("Wave-Particle Duality",    3),
    ("Krebs Cycle",              4),
    # earlier history
    ("Conservation of Energy",  13),
    ("DNA Replication",         19),
    ("Integration by Parts",    15),
    ("Derivatives (Chain Rule)", 20),
    ("Supply & Demand Curves",  17),
    ("Newton's Laws of Motion", 23),
    ("Limits & Continuity",     25),
    ("Binary Search Trees",     14),
    ("Recursion",               18),
    ("Big-O Notation",          22),
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

    # ── Insert sessions (for streak + history graphs) ────────────────────────
    for concept_name, days_ago in DEMO_SESSIONS:
        ended_at = (now - timedelta(days=days_ago)).replace(
            hour=18, minute=30, second=0, microsecond=0
        ).isoformat()
        concept_id = concept_ids.get(concept_name, "")
        # Only mark as "cleared" for concepts that are actually cleared
        status_row = next(
            (s for n, _, s, *_ in DEMO_CONCEPTS if n == concept_name), "on-loan"
        )
        outcome = "cleared" if status_row == "clear" else "attempted"
        conn.execute(
            """INSERT INTO sessions
               (id, student_id, concept_id, concept_name, outcome, ended_at)
               VALUES (?,?,?,?,?,?)""",
            [str(uuid.uuid4()), student_id, concept_id, concept_name, outcome, ended_at],
        )

    conn.commit()
    conn.close()
