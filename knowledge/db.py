import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from . import config

VALID_STATUSES = {"borrowed", "on_loan", "clear", "owned", "persists"}

def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
    """Return rows as dictionaries."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def get_connection() -> sqlite3.Connection:
    """Returns a new DB connection with dict_factory and enabled foreign keys."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Creates database, required tables, and indexes if they don't exist."""
    try:
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS debt_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept TEXT NOT NULL,
                    source_text TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confidence REAL,
                    status TEXT DEFAULT 'on_loan'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clearing_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept TEXT NOT NULL,
                    session_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    result TEXT,
                    notes TEXT
                )
            """)
            # Classroom integration tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS classroom_sessions (
                    session_id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    assignment_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    attachment_id TEXT,
                    submission_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deadline_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    student_id TEXT PRIMARY KEY,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    expires_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_debt_status ON debt_log(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_debt_concept ON debt_log(concept)
            """)
    except sqlite3.Error as e:
        raise RuntimeError(f"Database initialization error: {e}") from e


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _try_add_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    try:
        if not _column_exists(conn, table, column):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
    except Exception:
        # Safe migration rule: skip silently if already exists or unsupported.
        pass


def run_migrations() -> None:
    """Runs non-destructive schema migrations. Safe to call repeatedly."""
    with get_connection() as conn:
        # debt_log integrity columns
        _try_add_column(conn, "debt_log", "integrity_suspect", "integrity_suspect BOOL DEFAULT FALSE")
        _try_add_column(conn, "debt_log", "clearing_method", "clearing_method TEXT")
        _try_add_column(conn, "debt_log", "lens_signature", "lens_signature TEXT")

        # clearing_history integrity columns
        _try_add_column(conn, "clearing_history", "session_hash", "session_hash TEXT")
        _try_add_column(conn, "clearing_history", "spoof_attempts", "spoof_attempts INTEGER DEFAULT 0")
        _try_add_column(conn, "clearing_history", "paste_detected", "paste_detected BOOL DEFAULT FALSE")
        _try_add_column(conn, "clearing_history", "integrity_suspect", "integrity_suspect BOOL DEFAULT FALSE")
        _try_add_column(conn, "clearing_history", "voice_mode", "voice_mode BOOL DEFAULT FALSE")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                synced_at TEXT,
                course_id TEXT,
                week TEXT,
                concepts_shared INTEGER,
                payload_hash TEXT,
                status TEXT,
                server_acknowledged BOOL DEFAULT FALSE
            )
        """)
        _try_add_column(conn, "sync_audit", "synced_at", "synced_at TEXT")
        _try_add_column(conn, "sync_audit", "course_id", "course_id TEXT")
        _try_add_column(conn, "sync_audit", "week", "week TEXT")
        _try_add_column(conn, "sync_audit", "concepts_shared", "concepts_shared INTEGER")
        _try_add_column(conn, "sync_audit", "payload_hash", "payload_hash TEXT")
        _try_add_column(conn, "sync_audit", "status", "status TEXT")
        _try_add_column(conn, "sync_audit", "server_acknowledged", "server_acknowledged BOOL DEFAULT FALSE")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_pending (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                course_id TEXT,
                week TEXT,
                payload_json TEXT NOT NULL,
                payload_hash TEXT,
                last_error TEXT
            )
        """)
        _try_add_column(conn, "sync_pending", "created_at", "created_at TEXT DEFAULT CURRENT_TIMESTAMP")
        _try_add_column(conn, "sync_pending", "course_id", "course_id TEXT")
        _try_add_column(conn, "sync_pending", "week", "week TEXT")
        _try_add_column(conn, "sync_pending", "payload_json", "payload_json TEXT")
        _try_add_column(conn, "sync_pending", "payload_hash", "payload_hash TEXT")
        _try_add_column(conn, "sync_pending", "last_error", "last_error TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_fingerprints (
                session_id TEXT PRIMARY KEY,
                concept TEXT,
                total_duration_seconds INTEGER,
                turn_count INTEGER,
                response_times TEXT,
                response_lengths TEXT,
                timeout_count INTEGER,
                median_response_time REAL,
                response_time_variance REAL,
                backspace_events INTEGER,
                paste_detected BOOL,
                language_detected TEXT,
                session_hash TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS solo_sessions (
                session_id TEXT PRIMARY KEY,
                concept TEXT NOT NULL,
                question TEXT NOT NULL,
                started_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT DEFAULT 'active'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS real_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                concept TEXT NOT NULL,
                mode TEXT NOT NULL,
                score INTEGER,
                reasoning TEXT,
                specific_gaps TEXT,
                question TEXT,
                response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                concept_being_studied TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS concept_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                concept TEXT NOT NULL,
                direct_answer_score REAL DEFAULT 0.0,
                temporal_score REAL DEFAULT 0.0,
                probe_depth_score REAL DEFAULT 0.0,
                trap_score REAL DEFAULT 0.0,
                true_comprehension REAL DEFAULT 0.0,
                status TEXT DEFAULT 'unverified',
                verification_signal REAL DEFAULT 0.0,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                UNIQUE(session_id, concept)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                session_id TEXT,
                student_id TEXT,
                concept TEXT,
                inputs_json TEXT,
                decision_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS probe_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                concept TEXT NOT NULL,
                strategy TEXT NOT NULL,
                probe_text TEXT NOT NULL,
                is_wrong_trap BOOL DEFAULT FALSE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved BOOL DEFAULT FALSE,
                student_corrected BOOL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS socratic_interrupts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                concept TEXT NOT NULL,
                student_excerpt TEXT,
                probe_text TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved BOOL DEFAULT FALSE,
                resolved_at TEXT,
                penalized BOOL DEFAULT FALSE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_aliases (
                client_session_id TEXT PRIMARY KEY,
                db_session_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (db_session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)


def seed_demo_data_if_empty() -> bool:
    """Seed realistic two-week demo rows on fresh/empty databases."""
    with get_connection() as conn:
        existing = conn.execute("SELECT COUNT(*) AS n FROM debt_log").fetchone()["n"]
        if existing and existing > 0:
            return False

        rows = [
            ("Research Capstone Project", "Missing clear hypothesis in the proposal", 0.92, "on_loan", "-13 days"),
            ("AP English 12 Themes", "Confused central theme of the assigned literature", 0.87, "persists", "-12 days"),
            ("Calculus AB Limits", "Incorrect evaluation of limits at infinity", 0.78, "clear", "-11 days"),
            ("Biology Lab Analysis", "Failed to properly identify the cellular structures", 0.84, "clear", "-10 days"),
            ("World History Revolutions", "Could not explain the socioeconomic causes", 0.81, "on_loan", "-9 days"),
            ("Civics & Government", "Misidentified checks and balances in action", 0.89, "on_loan", "-7 days"),
            ("Physics Mechanics", "Newton's laws misapplied in free body diagram", 0.76, "persists", "-5 days"),
            ("Chemistry Bonding", "Covalent vs ionic properties confused", 0.74, "on_loan", "-2 days"),
        ]

        for concept, source_text, confidence, status, offset in rows:
            conn.execute(
                """
                INSERT INTO debt_log (concept, source_text, confidence, status, timestamp)
                VALUES (?, ?, ?, ?, datetime('now', ?))
                """,
                (concept, source_text, confidence, status, offset),
            )
        return True


def insert_clearing_history(
    concept: str,
    result: str,
    notes: str,
    session_hash: Optional[str] = None,
    spoof_attempts: int = 0,
    paste_detected: bool = False,
    integrity_suspect: bool = False,
    voice_mode: bool = False,
):
    """Logs the result of a clearing session."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO clearing_history
                    (concept, result, notes, session_hash, spoof_attempts, paste_detected, integrity_suspect, voice_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (concept, result, notes, session_hash, spoof_attempts, int(paste_detected), int(integrity_suspect), int(voice_mode)),
            )
    except sqlite3.Error as e:
        print(f"Error adding clearing history: {e}")


def set_debt_integrity(concept: str, integrity_suspect: bool, clearing_method: Optional[str] = None, lens_signature: Optional[str] = None) -> None:
    with get_connection() as conn:
        sets = ["integrity_suspect = ?"]
        values: List[Any] = [int(integrity_suspect)]
        if clearing_method is not None:
            sets.append("clearing_method = ?")
            values.append(clearing_method)
        if lens_signature is not None:
            sets.append("lens_signature = ?")
            values.append(lens_signature)
        values.append(concept)
        conn.execute(f"UPDATE debt_log SET {', '.join(sets)} WHERE concept = ?", values)


def list_sync_concepts() -> List[Dict[str, Any]]:
    """Returns latest per-concept rows needed for privacy-preserving sync."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT concept, status, COALESCE(clearing_method, '') AS clearing_method,
                   COALESCE(lens_signature, '') AS lens_signature,
                   COALESCE(integrity_suspect, 0) AS integrity_suspect
            FROM debt_log
            WHERE id IN (SELECT MAX(id) FROM debt_log GROUP BY concept)
            ORDER BY concept ASC
            """
        ).fetchall()


def write_sync_audit(course_id: str, week: str, concepts_shared: int, payload_hash: str, status: str, server_acknowledged: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sync_audit (synced_at, course_id, week, concepts_shared, payload_hash, status, server_acknowledged)
            VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
            """,
            (course_id, week, concepts_shared, payload_hash, status, int(server_acknowledged)),
        )


def get_sync_audit_log() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM sync_audit ORDER BY id DESC"
        ).fetchall()


def queue_sync_payload(course_id: str, week: str, payload_json: str, payload_hash: str, last_error: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sync_pending (course_id, week, payload_json, payload_hash, last_error)
            VALUES (?, ?, ?, ?, ?)
            """,
            (course_id, week, payload_json, payload_hash, last_error[:500]),
        )


def get_pending_sync_payloads() -> List[Dict[str, Any]]:
    try:
        with get_connection() as conn:
            return conn.execute("SELECT * FROM sync_pending ORDER BY id ASC").fetchall()
    except sqlite3.OperationalError:
        run_migrations()
        with get_connection() as conn:
            return conn.execute("SELECT * FROM sync_pending ORDER BY id ASC").fetchall()


def remove_pending_sync(sync_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM sync_pending WHERE id = ?", (sync_id,))


def save_session_fingerprint(row: Dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO session_fingerprints
                (session_id, concept, total_duration_seconds, turn_count, response_times, response_lengths,
                 timeout_count, median_response_time, response_time_variance, backspace_events,
                 paste_detected, language_detected, session_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                concept = excluded.concept,
                total_duration_seconds = excluded.total_duration_seconds,
                turn_count = excluded.turn_count,
                response_times = excluded.response_times,
                response_lengths = excluded.response_lengths,
                timeout_count = excluded.timeout_count,
                median_response_time = excluded.median_response_time,
                response_time_variance = excluded.response_time_variance,
                backspace_events = excluded.backspace_events,
                paste_detected = excluded.paste_detected,
                language_detected = excluded.language_detected,
                session_hash = excluded.session_hash,
                created_at = CURRENT_TIMESTAMP
            """,
            (
                row.get("session_id"),
                row.get("concept"),
                row.get("total_duration_seconds", 0),
                row.get("turn_count", 0),
                json.dumps(row.get("response_times", [])),
                json.dumps(row.get("response_lengths", [])),
                row.get("timeout_count", 0),
                row.get("median_response_time", 0.0),
                row.get("response_time_variance", 0.0),
                row.get("backspace_events", 0),
                int(bool(row.get("paste_detected", False))),
                row.get("language_detected", "unknown"),
                row.get("session_hash", ""),
            ),
        )


def get_session_fingerprint(session_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM session_fingerprints WHERE session_id = ?",
            (session_id,),
        ).fetchone()


def get_integrity_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        has_session_hash = _column_exists(conn, "clearing_history", "session_hash")
        has_spoof_attempts = _column_exists(conn, "clearing_history", "spoof_attempts")
        has_integrity_suspect = _column_exists(conn, "debt_log", "integrity_suspect")
        has_clearing_method = _column_exists(conn, "debt_log", "clearing_method")

        signed = conn.execute(
            "SELECT COUNT(*) AS n FROM clearing_history WHERE session_hash IS NOT NULL AND session_hash != ''"
            if has_session_hash else
            "SELECT 0 AS n"
        ).fetchone()["n"]
        total_hist = conn.execute("SELECT COUNT(*) AS n FROM clearing_history").fetchone()["n"]
        spoof_attempts = conn.execute(
            "SELECT COALESCE(SUM(spoof_attempts), 0) AS n FROM clearing_history"
            if has_spoof_attempts else
            "SELECT 0 AS n"
        ).fetchone()["n"]
        flagged = conn.execute(
            "SELECT COUNT(*) AS n FROM debt_log WHERE COALESCE(integrity_suspect, 0) = 1"
            if has_integrity_suspect else
            "SELECT 0 AS n"
        ).fetchone()["n"]
        lens_verified = conn.execute(
            "SELECT COUNT(*) AS n FROM debt_log WHERE clearing_method = 'lens_verified'"
            if has_clearing_method else
            "SELECT 0 AS n"
        ).fetchone()["n"]
        lens_total = conn.execute(
            "SELECT COUNT(*) AS n FROM debt_log WHERE clearing_method IN ('lens_verified', 'sage_only')"
            if has_clearing_method else
            "SELECT 0 AS n"
        ).fetchone()["n"]
    return {
        "sessions_with_signatures": signed,
        "sessions_total": total_hist,
        "lens_verified_genuine": lens_verified,
        "lens_verified_total": lens_total,
        "spoof_attempts": spoof_attempts,
        "flagged_concepts": flagged,
    }


def create_solo_session(session_id: str, concept: str, question: str, started_at: str, expires_at: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO solo_sessions (session_id, concept, question, started_at, expires_at, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            """,
            (session_id, concept, question, started_at, expires_at),
        )


def get_solo_session(session_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM solo_sessions WHERE session_id = ?", (session_id,)).fetchone()


def update_solo_session_status(session_id: str, status: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE solo_sessions SET status = ? WHERE session_id = ?", (status, session_id))


def get_prior_solo_questions(concept: str) -> List[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT question FROM real_performance WHERE concept = ? AND mode = 'solo' AND question IS NOT NULL",
            (concept,),
        ).fetchall()
    return [r["question"] for r in rows if r.get("question")]


def save_real_performance(session_id: str, concept: str, mode: str, score: int, reasoning: str, specific_gaps: List[str], question: str, response: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO real_performance (session_id, concept, mode, score, reasoning, specific_gaps, question, response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, concept, mode, score, reasoning, json.dumps(specific_gaps), question, response),
        )
        return cursor.lastrowid


def create_learning_session(student_id: str, concept_being_studied: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO sessions (student_id, started_at, concept_being_studied)
            VALUES (?, CURRENT_TIMESTAMP, ?)
            """,
            (student_id, concept_being_studied),
        )
        return int(cursor.lastrowid)


def get_or_create_learning_session(student_id: str, concept_being_studied: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id FROM sessions
            WHERE student_id = ? AND concept_being_studied = ?
            ORDER BY id DESC LIMIT 1
            """,
            (student_id, concept_being_studied),
        ).fetchone()
        if row and row.get("id") is not None:
            return int(row["id"])
    return create_learning_session(student_id, concept_being_studied)


def set_session_alias(client_session_id: str, db_session_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO session_aliases (client_session_id, db_session_id)
            VALUES (?, ?)
            ON CONFLICT(client_session_id) DO UPDATE SET db_session_id = excluded.db_session_id
            """,
            (client_session_id, db_session_id),
        )


def get_db_session_id_from_alias(client_session_id: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT db_session_id FROM session_aliases WHERE client_session_id = ?",
            (client_session_id,),
        ).fetchone()
    if not row:
        return None
    return int(row.get("db_session_id"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def get_concept_score(session_id: int, concept: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM concept_scores WHERE session_id = ? AND concept = ?",
            (session_id, concept),
        ).fetchone()


def upsert_concept_score(
    session_id: int,
    concept: str,
    direct_answer_score: float,
    temporal_score: float,
    probe_depth_score: float,
    trap_score: float,
    true_comprehension: float,
    status: str,
    verification_signal: float = 0.0,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO concept_scores
                (session_id, concept, direct_answer_score, temporal_score, probe_depth_score,
                 trap_score, true_comprehension, status, verification_signal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, concept) DO UPDATE SET
                direct_answer_score = excluded.direct_answer_score,
                temporal_score = excluded.temporal_score,
                probe_depth_score = excluded.probe_depth_score,
                trap_score = excluded.trap_score,
                true_comprehension = excluded.true_comprehension,
                status = excluded.status,
                verification_signal = excluded.verification_signal
            """,
            (
                session_id,
                concept,
                direct_answer_score,
                temporal_score,
                probe_depth_score,
                trap_score,
                true_comprehension,
                status,
                verification_signal,
            ),
        )


def update_comprehension_score(session_id: int, concept: str, new_signal: Dict[str, Any]) -> Dict[str, Any]:
    from .anti_gaming import compute_true_comprehension, derive_comprehension_status

    current = get_concept_score(session_id, concept) or {}
    direct_answer_score = _safe_float(new_signal.get("direct_answer_score", current.get("direct_answer_score", 0.0)))
    temporal_score = _safe_float(new_signal.get("temporal_score", current.get("temporal_score", 0.0)))
    probe_depth_score = _safe_float(new_signal.get("probe_depth_score", current.get("probe_depth_score", 0.0)))
    trap_score = _safe_float(new_signal.get("trap_score", current.get("trap_score", 0.0)))
    verification_signal = _safe_float(new_signal.get("verification_signal", current.get("verification_signal", 0.0)))

    true_comprehension = compute_true_comprehension(
        direct_answer_score=direct_answer_score,
        temporal_score=temporal_score,
        probe_depth_score=probe_depth_score,
        trap_score=trap_score,
    )
    status = derive_comprehension_status(
        true_comprehension=true_comprehension,
        diagram_verified=verification_signal >= 0.6,
    )

    upsert_concept_score(
        session_id=session_id,
        concept=concept,
        direct_answer_score=direct_answer_score,
        temporal_score=temporal_score,
        probe_depth_score=probe_depth_score,
        trap_score=trap_score,
        true_comprehension=true_comprehension,
        status=status,
        verification_signal=verification_signal,
    )

    return {
        "session_id": session_id,
        "concept": concept,
        "direct_answer_score": direct_answer_score,
        "temporal_score": temporal_score,
        "probe_depth_score": probe_depth_score,
        "trap_score": trap_score,
        "verification_signal": verification_signal,
        "true_comprehension": true_comprehension,
        "status": status,
    }


def get_student_debt_report(student_id: str) -> Dict[str, List[Dict[str, Any]]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cs.*, s.student_id
            FROM concept_scores cs
            JOIN sessions s ON s.id = cs.session_id
            WHERE s.student_id = ? AND cs.true_comprehension < 0.6
            ORDER BY cs.true_comprehension ASC
            """,
            (student_id,),
        ).fetchall()

    grouped: Dict[str, List[Dict[str, Any]]] = {
        "live_session_required": [],
        "unverified": [],
        "shallow": [],
    }
    for row in rows:
        status = row.get("status", "unverified")
        grouped.setdefault(status, []).append(row)
    return grouped


def log_audit_event(
    event_type: str,
    session_id: Optional[str],
    student_id: Optional[str],
    concept: Optional[str],
    inputs: Dict[str, Any],
    decision: Dict[str, Any],
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (event_type, session_id, student_id, concept, inputs_json, decision_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                session_id,
                student_id,
                concept,
                json.dumps(inputs, sort_keys=True),
                json.dumps(decision, sort_keys=True),
            ),
        )


def register_probe(session_id: str, concept: str, strategy: str, probe_text: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO probe_registry (session_id, concept, strategy, probe_text, is_wrong_trap)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, concept, strategy, probe_text, int(strategy == "WRONG_TRAP")),
        )
        return int(cursor.lastrowid)


def resolve_probe(probe_id: int, student_corrected: Optional[bool]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE probe_registry
            SET resolved = 1, student_corrected = ?, created_at = created_at
            WHERE id = ?
            """,
            (None if student_corrected is None else int(student_corrected), probe_id),
        )


def get_pending_wrong_traps(session_id: str, concept: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM probe_registry
            WHERE session_id = ? AND concept = ? AND is_wrong_trap = 1 AND resolved = 0
            ORDER BY id DESC
            """,
            (session_id, concept),
        ).fetchall()


def register_socratic_interrupt(session_id: str, concept: str, student_excerpt: str, probe_text: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO socratic_interrupts (session_id, concept, student_excerpt, probe_text)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, concept, student_excerpt, probe_text),
        )
        return int(cursor.lastrowid)


def resolve_socratic_interrupts(session_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE socratic_interrupts
            SET resolved = 1, resolved_at = CURRENT_TIMESTAMP
            WHERE session_id = ? AND resolved = 0
            """,
            (session_id,),
        )


def mark_aborted_interrupts_and_penalize(idle_seconds: int = 300) -> int:
    threshold = (datetime.utcnow() - timedelta(seconds=idle_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    penalized = 0
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM socratic_interrupts
            WHERE resolved = 0 AND penalized = 0 AND created_at <= ?
            """,
            (threshold,),
        ).fetchall()

        for row in rows:
            session_row = conn.execute(
                "SELECT id FROM sessions WHERE id = ? LIMIT 1",
                (row.get("session_id"),),
            ).fetchone()
            if session_row:
                cs = conn.execute(
                    "SELECT probe_depth_score FROM concept_scores WHERE session_id = ? AND concept = ?",
                    (session_row["id"], row.get("concept")),
                ).fetchone()
                existing_depth = _safe_float(cs.get("probe_depth_score", 0.0) if cs else 0.0)
                penalized_depth = max(0.0, existing_depth - 0.2)
                from .anti_gaming import compute_true_comprehension, derive_comprehension_status
                full = conn.execute(
                    "SELECT * FROM concept_scores WHERE session_id = ? AND concept = ?",
                    (session_row["id"], row.get("concept")),
                ).fetchone() or {}
                direct = _safe_float(full.get("direct_answer_score", 0.0))
                temporal = _safe_float(full.get("temporal_score", 0.0))
                trap = _safe_float(full.get("trap_score", 0.0))
                verification_signal = _safe_float(full.get("verification_signal", 0.0))
                true_comp = compute_true_comprehension(direct, temporal, penalized_depth, trap)
                status = derive_comprehension_status(true_comp, diagram_verified=verification_signal >= 0.6)
                conn.execute(
                    """
                    INSERT INTO concept_scores
                        (session_id, concept, direct_answer_score, temporal_score, probe_depth_score,
                         trap_score, true_comprehension, status, verification_signal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id, concept) DO UPDATE SET
                        direct_answer_score = excluded.direct_answer_score,
                        temporal_score = excluded.temporal_score,
                        probe_depth_score = excluded.probe_depth_score,
                        trap_score = excluded.trap_score,
                        true_comprehension = excluded.true_comprehension,
                        status = excluded.status,
                        verification_signal = excluded.verification_signal
                    """,
                    (
                        session_row["id"],
                        row.get("concept"),
                        direct,
                        temporal,
                        penalized_depth,
                        trap,
                        true_comp,
                        status,
                        verification_signal,
                    ),
                )
                penalized += 1

            conn.execute(
                "UPDATE socratic_interrupts SET penalized = 1 WHERE id = ?",
                (row["id"],),
            )
    return penalized


def penalize_open_interrupts_for_session(session_id: str) -> int:
    penalized = 0
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM socratic_interrupts
            WHERE session_id = ? AND resolved = 0 AND penalized = 0
            """,
            (session_id,),
        ).fetchall()
        for row in rows:
            session_row = conn.execute(
                "SELECT id FROM sessions WHERE id = ? LIMIT 1",
                (session_id,),
            ).fetchone()
            if session_row:
                cs = conn.execute(
                    "SELECT probe_depth_score FROM concept_scores WHERE session_id = ? AND concept = ?",
                    (session_row["id"], row.get("concept")),
                ).fetchone()
                existing_depth = _safe_float(cs.get("probe_depth_score", 0.0) if cs else 0.0)
                penalized_depth = max(0.0, existing_depth - 0.2)
                from .anti_gaming import compute_true_comprehension, derive_comprehension_status
                full = conn.execute(
                    "SELECT * FROM concept_scores WHERE session_id = ? AND concept = ?",
                    (session_row["id"], row.get("concept")),
                ).fetchone() or {}
                direct = _safe_float(full.get("direct_answer_score", 0.0))
                temporal = _safe_float(full.get("temporal_score", 0.0))
                trap = _safe_float(full.get("trap_score", 0.0))
                verification_signal = _safe_float(full.get("verification_signal", 0.0))
                true_comp = compute_true_comprehension(direct, temporal, penalized_depth, trap)
                status = derive_comprehension_status(true_comp, diagram_verified=verification_signal >= 0.6)
                conn.execute(
                    """
                    INSERT INTO concept_scores
                        (session_id, concept, direct_answer_score, temporal_score, probe_depth_score,
                         trap_score, true_comprehension, status, verification_signal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id, concept) DO UPDATE SET
                        direct_answer_score = excluded.direct_answer_score,
                        temporal_score = excluded.temporal_score,
                        probe_depth_score = excluded.probe_depth_score,
                        trap_score = excluded.trap_score,
                        true_comprehension = excluded.true_comprehension,
                        status = excluded.status,
                        verification_signal = excluded.verification_signal
                    """,
                    (
                        session_row["id"],
                        row.get("concept"),
                        direct,
                        temporal,
                        penalized_depth,
                        trap,
                        true_comp,
                        status,
                        verification_signal,
                    ),
                )
            conn.execute(
                "UPDATE socratic_interrupts SET penalized = 1, resolved = 1, resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
                (row["id"],),
            )
            penalized += 1
    return penalized


def get_real_performance_by_session(session_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM real_performance WHERE session_id = ? ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()


def get_before_after(concept: str) -> Dict[str, Optional[int]]:
    with get_connection() as conn:
        assisted = conn.execute(
            "SELECT score FROM real_performance WHERE concept = ? AND mode = 'assisted' ORDER BY id ASC LIMIT 1",
            (concept,),
        ).fetchone()
        solo = conn.execute(
            "SELECT score FROM real_performance WHERE concept = ? AND mode = 'solo' ORDER BY id DESC LIMIT 1",
            (concept,),
        ).fetchone()
    before = assisted["score"] if assisted else None
    after = solo["score"] if solo else None
    return {"before": before, "after": after, "delta": (after - before) if before is not None and after is not None else None}

def insert_debt(concept: str, source_text: str, confidence: float) -> int:
    """
    Inserts a new debt entry and returns its ID.
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO debt_log (concept, source_text, confidence, status)
                VALUES (?, ?, ?, 'on_loan')
            """, (concept, source_text, confidence))
            return cursor.lastrowid
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to add debt entry: {e}") from e

def update_status(concept: str, status: str) -> int:
    """
    Updates status for a specific concept.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: '{status}'. Must be one of {VALID_STATUSES}")
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                UPDATE debt_log
                SET status = ?
                WHERE concept = ? AND status IN ('borrowed', 'on_loan')
            """, (status, concept))
            return cursor.rowcount
    except sqlite3.Error as e:
        print(f"Error updating status for concept {concept}: {e}")
        return 0

def get_debt_by_concept(concept: str) -> List[Dict[str, Any]]:
    """Retrieves all debt entries for a given concept."""
    try:
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM debt_log WHERE concept = ? ORDER BY timestamp DESC", (concept,)
            ).fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching debt by concept {concept}: {e}")
        return []

def get_all_active_debt(include_legacy: bool = False) -> List[Dict[str, Any]]:
    """Retrieves active debt entries. Legacy 'borrowed' rows are hidden by default."""
    try:
        with get_connection() as conn:
            statuses = "'on_loan', 'clear', 'persists'" if not include_legacy else "'borrowed', 'on_loan', 'clear', 'persists'"
            return conn.execute(
                f"SELECT * FROM debt_log WHERE status IN ({statuses}) ORDER BY timestamp DESC"
            ).fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching active debts: {e}")
        return []

def get_all_debt() -> List[Dict[str, Any]]:
    """Retrieves all debt entries."""
    try:
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM debt_log ORDER BY timestamp DESC"
            ).fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching all debts: {e}")
        return []

def get_class_heatmap(include_legacy: bool = False) -> List[Dict[str, Any]]:
    """
    Anonymized aggregate counts per concept across the entire class/log.
    Returns concepts grouped by their current active borrowed count, for Instructor view.
    """
    try:
        with get_connection() as conn:
            statuses = "'on_loan', 'clear', 'persists'" if not include_legacy else "'borrowed', 'on_loan', 'clear', 'persists'"
            return conn.execute("""
                SELECT concept, COUNT(*) as count 
                FROM debt_log 
                WHERE status IN (""" + statuses + """)
                GROUP BY concept
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching heatmap: {e}")
        return []

# Analytical Functions for Progress & Reports Tabs

def get_progress_over_time(days: int = 30) -> List[Dict[str, Any]]:
    """
    Returns one row per day for the past `days` days.
    Each row has counts of on_loan, clear/owned, and persists entries,
    plus a debt_score (on_loan + persists as % of total active entries that day).
    """
    from datetime import datetime, timedelta
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    strftime('%Y-%m-%d', timestamp) AS day,
                    SUM(CASE WHEN status = 'on_loan' THEN 1 ELSE 0 END)              AS on_loan,
                    SUM(CASE WHEN status IN ('clear', 'owned') THEN 1 ELSE 0 END)   AS owned,
                    SUM(CASE WHEN status = 'persists' THEN 1 ELSE 0 END)            AS persists
                FROM debt_log
                WHERE timestamp >= date('now', ? || ' days')
                GROUP BY day
                ORDER BY day ASC
            """, (f"-{days}",)).fetchall()
    except Exception:
        rows = []

    # Build a complete calendar (fill gaps with zeros)
    base = datetime.now().date() - timedelta(days=days - 1)
    indexed = {r["day"]: r for r in rows}
    data = []
    for i in range(days):
        day = (base + timedelta(days=i)).isoformat()
        r = indexed.get(day, {"on_loan": 0, "owned": 0, "persists": 0})
        total = (r["on_loan"] or 0) + (r["owned"] or 0) + (r["persists"] or 0)
        debt_score = round(((r["on_loan"] or 0) + (r["persists"] or 0)) / total * 100) if total else 0
        data.append({
            "date": (base + timedelta(days=i)).strftime("%b %d"),
            "debt_score": debt_score,
            "owned":   r["owned"]   or 0,
            "on_loan": r["on_loan"] or 0,
            "persists": r["persists"] or 0,
        })
    return data


def get_clearing_velocity(days: int = 14) -> List[Dict[str, Any]]:
    """
    How many concepts were cleared (status moved to 'clear' or 'owned') per day,
    proxied by counting clearing_history entries per day.
    """
    from datetime import datetime, timedelta
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT strftime('%Y-%m-%d', session_ts) AS day, COUNT(*) AS cleared_count
                FROM clearing_history
                WHERE session_ts >= date('now', ? || ' days')
                  AND result IN ('clear', 'cleared', 'owned')
                GROUP BY day
                ORDER BY day ASC
            """, (f"-{days}",)).fetchall()
    except Exception:
        rows = []

    base = datetime.now().date() - timedelta(days=days - 1)
    indexed = {r["day"]: r["cleared_count"] for r in rows}
    data = []
    for i in range(days):
        day = (base + timedelta(days=i)).isoformat()
        data.append({
            "date": (base + timedelta(days=i)).strftime("%b %d"),
            "cleared_count": indexed.get(day, 0),
        })
    return data


def get_concept_time_to_clear() -> List[Dict[str, Any]]:
    """
    For each concept, compute average days between first debt entry and first clear entry.
    Falls back to showing concepts still on_loan with no clear date (days_to_clear = None).
    """
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    concept,
                    status,
                    MIN(timestamp) AS first_seen,
                    MAX(CASE WHEN status IN ('clear', 'owned') THEN timestamp END) AS first_cleared
                FROM debt_log
                GROUP BY concept
                ORDER BY first_seen DESC
                LIMIT 20
            """).fetchall()
    except Exception:
        return []

    result = []
    for r in rows:
        days_to_clear = None
        if r["first_cleared"] and r["first_seen"]:
            try:
                from datetime import datetime
                t0 = datetime.fromisoformat(r["first_seen"])
                t1 = datetime.fromisoformat(r["first_cleared"])
                days_to_clear = max(0, round((t1 - t0).total_seconds() / 86400, 1))
            except Exception:
                days_to_clear = None
        result.append({
            "concept": r["concept"],
            "days_to_clear": days_to_clear,
            "subject": "General",   # subject field not yet in schema
            "status": r["status"],
        })
    return result


def get_subject_breakdown() -> List[Dict[str, Any]]:
    """
    Groups concepts by status to give a breakdown of the overall debt landscape.
    (Subject tagging is not yet in the schema; returns a single group for now.)
    """
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    status,
                    COUNT(DISTINCT concept) AS concept_count
                FROM debt_log
                WHERE status IN ('on_loan', 'clear', 'owned', 'persists')
                GROUP BY status
            """).fetchall()
    except Exception:
        return []

    counts = {r["status"]: r["concept_count"] for r in rows}
    total = sum(counts.values()) or 1
    on_loan  = counts.get("on_loan",  0)
    owned    = counts.get("clear",    0) + counts.get("owned", 0)
    persists = counts.get("persists", 0)
    debt_score = round((on_loan + persists) / total * 100)
    return [
        {"subject": "All Concepts", "on_loan": on_loan, "owned": owned, "persists": persists, "debt_score": debt_score},
    ]


def get_weekly_report(student_id: str) -> Dict[str, Any]:
    """
    Summarises activity over the last 7 days vs the 7 days before that.
    """
    try:
        with get_connection() as conn:
            # New debt added in last 7 days
            new_debt = conn.execute("""
                SELECT COUNT(*) AS n FROM debt_log
                WHERE timestamp >= date('now', '-7 days')
            """).fetchone()["n"]

            # Concepts cleared in the last 7 days (clearing_history)
            cleared = conn.execute("""
                SELECT COUNT(*) AS n FROM clearing_history
                WHERE session_ts >= date('now', '-7 days')
                  AND result IN ('clear', 'cleared', 'owned')
            """).fetchone()["n"]

            # Most-borrowed concept overall
            top = conn.execute("""
                SELECT concept, COUNT(*) AS n FROM debt_log
                GROUP BY concept ORDER BY n DESC LIMIT 1
            """).fetchone()
            top_concept = top["concept"] if top else "—"

            # Streak: distinct days in clearing_history in the last 30 days
            streak_rows = conn.execute("""
                SELECT DISTINCT strftime('%Y-%m-%d', session_ts) AS day
                FROM clearing_history
                WHERE session_ts >= date('now', '-30 days')
                  AND result IN ('clear', 'cleared', 'owned')
                ORDER BY day DESC
            """).fetchall()
            streak_days = _compute_streak([r["day"] for r in streak_rows])

            # Debt scores (simple: active / total)
            total_now  = conn.execute("SELECT COUNT(*) AS n FROM debt_log WHERE status IN ('on_loan','persists','clear','owned')").fetchone()["n"] or 1
            active_now = conn.execute("SELECT COUNT(*) AS n FROM debt_log WHERE status IN ('on_loan','persists')").fetchone()["n"]
            curr_debt_score = round(active_now / total_now * 100)

            # Previous week snapshot
            total_prev  = conn.execute("""
                SELECT COUNT(*) AS n FROM debt_log
                WHERE timestamp <= date('now', '-7 days')
                  AND status IN ('on_loan','persists','clear','owned')
            """).fetchone()["n"] or 1
            active_prev = conn.execute("""
                SELECT COUNT(*) AS n FROM debt_log
                WHERE timestamp <= date('now', '-7 days')
                  AND status IN ('on_loan','persists')
            """).fetchone()["n"]
            prev_debt_score = round(active_prev / total_prev * 100)

    except Exception:
        return {
            "cleared_this_week": 0, "new_debt": 0, "net_change": 0,
            "top_concept": "—", "streak_days": 0,
            "prev_debt_score": 0, "curr_debt_score": 0,
        }

    return {
        "cleared_this_week": cleared,
        "new_debt": new_debt,
        "net_change": new_debt - cleared,
        "top_concept": top_concept,
        "streak_days": streak_days,
        "prev_debt_score": prev_debt_score,
        "curr_debt_score": curr_debt_score,
    }


def _compute_streak(days_desc: list) -> int:
    """Counts consecutive days (including today) from a DESC-sorted list of 'YYYY-MM-DD' strings."""
    from datetime import date, timedelta
    if not days_desc:
        return 0
    streak = 0
    expected = date.today()
    for day_str in days_desc:
        try:
            d = date.fromisoformat(day_str)
        except ValueError:
            continue
        if d == expected or d == expected - timedelta(days=1):
            streak += 1
            expected = d - timedelta(days=1)
        else:
            break
    return streak


def get_class_report_data() -> List[Dict[str, Any]]:
    """
    Per-concept class-wide analytics:
    - total_borrowed: how many times this concept was ever borrowed
    - total_cleared: how many entries reached 'clear' or 'owned'
    - avg_days_to_clear: mean days between insertion and clearing
    - persistence_rate: % of entries that ended up as 'persists'
    """
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    concept,
                    COUNT(*) AS total_borrowed,
                    SUM(CASE WHEN status IN ('clear','owned') THEN 1 ELSE 0 END) AS total_cleared,
                    SUM(CASE WHEN status = 'persists' THEN 1 ELSE 0 END) AS total_persists,
                    AVG(
                        CASE WHEN status IN ('clear','owned')
                        THEN ROUND((julianday('now') - julianday(timestamp)), 1)
                        END
                    ) AS avg_days_to_clear
                FROM debt_log
                GROUP BY concept
                ORDER BY total_borrowed DESC
                LIMIT 20
            """).fetchall()
    except Exception:
        return []

    result = []
    for r in rows:
        total = r["total_borrowed"] or 1
        result.append({
            "concept":           r["concept"],
            "total_borrowed":    r["total_borrowed"]  or 0,
            "total_cleared":     r["total_cleared"]   or 0,
            "avg_days_to_clear": round(r["avg_days_to_clear"] or 0, 1),
            "persistence_rate":  round((r["total_persists"] or 0) / total * 100),
        })
    return result

# ── Classroom session helpers ──────────────────────────────────────────────────

def create_classroom_session(
    session_id: str,
    student_id: str,
    assignment_id: str,
    course_id: str,
    deadline_at: str
) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO classroom_sessions
                (session_id, student_id, assignment_id, course_id, status, deadline_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (session_id, student_id, assignment_id, course_id, deadline_at))

def get_classroom_session(session_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM classroom_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

def update_session_status(session_id: str, status: str, **kwargs) -> None:
    """Update session status and any optional extra fields."""
    valid_extra = {"attachment_id", "submission_id"}
    sets = ["status = ?"]
    values = [status]
    for k, v in kwargs.items():
        if k in valid_extra:
            sets.append(f"{k} = ?")
            values.append(v)
    values.append(session_id)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE classroom_sessions SET {', '.join(sets)} WHERE session_id = ?",
            values
        )

def get_pending_sessions_past_deadline() -> List[Dict[str, Any]]:
    """Returns sessions that are still pending but past their 24h deadline."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT * FROM classroom_sessions
            WHERE status IN ('pending', 'debt_found')
              AND deadline_at <= CURRENT_TIMESTAMP
        """).fetchall()


# ── App settings helpers ───────────────────────────────────────────────────────

def get_app_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,)
        ).fetchone()
    if not row:
        return default
    return row.get("value", default)


def set_app_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value)
        )


def get_llm_settings() -> Dict[str, Optional[str]]:
    return {
        "ollama_base_url": get_app_setting("ollama_base_url") or get_app_setting("ollama_host"),
        "ollama_host": get_app_setting("ollama_base_url") or get_app_setting("ollama_host"),
        "scout_model": get_app_setting("scout_model"),
        "sage_model": get_app_setting("sage_model"),
        "lens_model": get_app_setting("lens_model"),
    }


def save_llm_settings(
    ollama_base_url: str,
    scout_model: str,
    sage_model: str,
    lens_model: str,
) -> None:
    set_app_setting("ollama_base_url", ollama_base_url)
    set_app_setting("ollama_host", ollama_base_url)
    set_app_setting("scout_model", scout_model)
    set_app_setting("sage_model", sage_model)
    set_app_setting("lens_model", lens_model)