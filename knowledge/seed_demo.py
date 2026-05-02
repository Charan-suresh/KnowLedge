"""
Demo seed data — gives the app a realistic, populated look for demonstrations.
Concepts are drawn from The Prairie School US Curriculum Guide (grades 9-12):
English, Mathematics, Biology, Chemistry, Physics, and US/World History.
Varied confidence levels, a 30-day history, and a 5-day clearing streak so
the Progress and Reports pages look compelling.
"""
import sqlite3
import uuid
from datetime import datetime, timedelta

from .init_db import DB_PATH

# ---------------------------------------------------------------------------
# (name, subject, status, confidence, days_ago_created, days_ago_cleared)
# days_ago_cleared is None for non-cleared concepts
# Drawn from the HS curriculum: Algebra 2 / Pre-calc / AP Calc, Biology,
# Chemistry, Honors Physics, US History, and English Lit.
# ---------------------------------------------------------------------------
DEMO_CONCEPTS = [
    # ── Mathematics: Algebra 2 & Pre-calculus ───────────────────────────────
    ("Linear Equations & Inequalities",    "Mathematics", "clear",    0.95, 30, 24),
    ("Quadratic Functions & the Parabola", "Mathematics", "clear",    0.91, 27, 20),
    ("Exponential & Logarithmic Functions","Mathematics", "clear",    0.87, 22, 15),
    ("Systems of Equations",               "Mathematics", "clear",    0.83, 18, 11),
    ("Polynomial Long Division",           "Mathematics", "on-loan",  0.58, 14, None),
    ("Rational Expressions & Asymptotes",  "Mathematics", "on-loan",  0.44, 10, None),
    ("Trigonometric Functions (sin/cos)",  "Mathematics", "persists", 0.32,  7, None),

    # ── Mathematics: AP Calculus AB/BC ──────────────────────────────────────
    ("Limits & Continuity",                "AP Calculus", "clear",    0.96, 29, 23),
    ("Derivatives & the Chain Rule",       "AP Calculus", "clear",    0.90, 25, 17),
    ("Definite Integrals (Riemann Sums)",  "AP Calculus", "clear",    0.84, 10,  4),  # cleared 4 days ago
    ("Fundamental Theorem of Calculus",    "AP Calculus", "clear",    0.79,  9,  3),  # cleared 3 days ago
    ("Related Rates",                      "AP Calculus", "on-loan",  0.50,  6, None),

    # ── Biology ─────────────────────────────────────────────────────────────
    ("Cell Structure & Function",          "Biology",     "clear",    0.93, 28, 21),
    ("DNA Replication & Transcription",    "Biology",     "clear",    0.89, 21, 13),
    ("Mendelian Genetics & Punnett Squares","Biology",    "clear",    0.85, 11,  1),  # cleared yesterday
    ("Natural Selection & Evolution",      "Biology",     "on-loan",  0.52,  8, None),
    ("Photosynthesis & Cellular Respiration","Biology",   "persists", 0.29,  5, None),

    # ── Chemistry ───────────────────────────────────────────────────────────
    ("Atomic Structure & the Periodic Table","Chemistry", "clear",    0.92, 26, 19),
    ("Ionic & Covalent Bonding",            "Chemistry",  "clear",    0.86, 20, 12),
    ("Stoichiometry & Mole Calculations",   "Chemistry",  "clear",    0.81,  8,  2),  # cleared 2 days ago
    ("Acids, Bases & pH",                   "Chemistry",  "on-loan",  0.47,  5, None),
    ("Chemical Equilibrium (Le Chatelier)", "Chemistry",  "persists", 0.26,  3, None),

    # ── Honors Physics ──────────────────────────────────────────────────────
    ("Newton's Laws of Motion",             "Physics",    "clear",    0.94, 27, 20),
    ("Conservation of Energy & Momentum",   "Physics",    "clear",    0.88, 19, 10),
    ("Wave Properties & the Doppler Effect","Physics",    "on-loan",  0.55,  9, None),
    ("Electrostatics & Coulomb's Law",      "Physics",    "persists", 0.33,  4, None),

    # ── US History ──────────────────────────────────────────────────────────
    ("Causes of the American Revolution",   "US History", "clear",    0.90, 24, 17),
    ("Constitutional Framework & Checks",   "US History", "clear",    0.87, 16,  8),
    ("Causes & Effects of the Civil War",   "US History", "clear",    0.80,  8,  0),  # cleared today
    ("The Progressive Era (1890–1920)",     "US History", "on-loan",  0.49,  6, None),
    ("Cold War & Containment Policy",       "US History", "persists", 0.30,  3, None),

    # ── English Literature ───────────────────────────────────────────────────
    ("Literary Analysis & Thesis Writing",  "English",    "clear",    0.91, 23, 15),
    ("Figurative Language & Symbolism",     "English",    "clear",    0.85, 13,  5),
    ("Persuasive Writing Techniques",       "English",    "on-loan",  0.53,  7, None),
    ("Narrative Structure & Point of View", "English",    "persists", 0.35,  4, None),
]

# ---------------------------------------------------------------------------
# Sessions — all outcome='cleared' so the streak counter and trend chart work.
# The first 5 entries cover today through 4 days ago → 5-day streak.
# ---------------------------------------------------------------------------
DEMO_SESSIONS = [
    # ── 5-day streak ─────────────────────────────────────────────────────────
    ("Causes & Effects of the Civil War",   0),   # today
    ("Mendelian Genetics & Punnett Squares",1),   # yesterday
    ("Stoichiometry & Mole Calculations",   2),
    ("Fundamental Theorem of Calculus",     3),
    ("Definite Integrals (Riemann Sums)",   4),
    # ── earlier history (populates the 30-day trend graph) ───────────────────
    ("Conservation of Energy & Momentum",  10),
    ("Ionic & Covalent Bonding",           12),
    ("Constitutional Framework & Checks",   8),
    ("DNA Replication & Transcription",    13),
    ("Newton's Laws of Motion",            20),
    ("Causes of the American Revolution",  17),
    ("Atomic Structure & the Periodic Table",19),
    ("Cell Structure & Function",          21),
    ("Literary Analysis & Thesis Writing", 15),
    ("Derivatives & the Chain Rule",       17),
    ("Limits & Continuity",                23),
    ("Exponential & Logarithmic Functions",15),
    ("Quadratic Functions & the Parabola", 20),
    ("Linear Equations & Inequalities",    24),
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
