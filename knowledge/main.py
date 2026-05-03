"""
Legacy cloud inference files removed during the Ollama cutover:
- check_hf.py
- upload_hf.py
- test_hf.py
- hf_requirements.txt
- legacy space deployment files
- knowledge/agents/hf_client.py
- tests/test_hf_client.py
- tests covering the old remote space contract
- old loading copy in the shared base template
- README.md
- TECHNICAL_ARCHITECTURE.md
- docs/TECHNICAL_PRESENTATION.html
"""

import base64
import json
import os
import re
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config
from . import db
from . import orchestrator
from . import ollama_client
from .agents.inference_router import is_ready as inference_ready
from .init_db import DB_PATH, init
from .anti_gaming import score_temporal_fingerprint
from .prompts import LENS_SYSTEM, SAGE_SYSTEM, SCOUT_SYSTEM, SOLO_SYSTEM
from .seed_demo import seed
from .sync import build_weekly_payload, send_weekly_payload

BASE_DIR = Path(__file__).resolve().parent
# Use HF Space URL as the default when running in hf_space backend mode
DEFAULT_OLLAMA_URL = (
    config.HF_SPACE_URL
    if config.INFERENCE_BACKEND == "hf_space" and config.HF_SPACE_URL
    else config.OLLAMA_BASE_URL
)
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"


def init_app() -> None:
    init()
    db.init_db()
    db.run_migrations()
    if DEMO_MODE:
        # Seed both "demo" and "default" so any visitor gets preloaded data
        # regardless of whether their browser has a prior cookie/localStorage entry.
        seed("demo")
        seed("default")


init_app()
app = FastAPI(title="KnowLedge")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_student_id(request: Request) -> str:
    stored = (request.cookies.get("student_id") or "").strip()
    if stored:
        return stored
    # In demo mode default to the pre-seeded demo account so pages aren't empty
    return "demo" if DEMO_MODE else "default"


def render_page(request: Request, template_name: str, extra: dict | None = None):
    context = {
        "request": request,
        "demo_mode": DEMO_MODE,
        "default_ollama_url": DEFAULT_OLLAMA_URL,
        "student_id": get_student_id(request),
        "inference_backend": config.INFERENCE_BACKEND,
        "hf_space_url": config.HF_SPACE_URL or "",
    }
    if extra:
        context.update(extra)
    return templates.TemplateResponse(request, template_name, context)


@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url="/ledger")


def _page_response(request: Request, template_name: str):
    """Render a page and, in DEMO_MODE, stamp the student_id cookie so the
    browser always queries the pre-seeded account even on a cold first visit."""
    response = render_page(request, template_name)
    if DEMO_MODE and not request.cookies.get("student_id"):
        sid = get_student_id(request)  # "demo" in DEMO_MODE
        response.set_cookie("student_id", sid, samesite="lax", max_age=365 * 86400)
    return response


@app.get("/ledger", response_class=HTMLResponse)
def ledger_page(request: Request):
    return _page_response(request, "ledger.html")


@app.get("/progress", response_class=HTMLResponse)
def progress_page(request: Request):
    return _page_response(request, "progress.html")


@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request):
    return _page_response(request, "reports.html")


@app.get("/help", response_class=HTMLResponse)
def help_page(request: Request):
    return _page_response(request, "help.html")


@app.get("/demo")
def demo_route():
    seed("demo", force=True)
    response = RedirectResponse(url="/ledger")
    response.set_cookie("student_id", "demo", samesite="lax")
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def status(ollama_url: str | None = Query(None)):
    return inference_ready(ollama_url or DEFAULT_OLLAMA_URL)


@app.get("/api/sync/status")
def sync_status():
    pending = db.get_pending_sync_payloads()
    audit = db.get_sync_audit_log()
    return {
        "pending_count": len(pending),
        "audit_count": len(audit),
        "last_status": audit[0]["status"] if audit else "idle",
    }


@app.get("/api/integrity/report")
def integrity_report():
    return db.get_integrity_summary()


@app.post("/api/sync/share-weekly")
def share_weekly():
    payload = build_weekly_payload()
    if config.UNIVERSITY_SERVER_URL:
        try:
            return send_weekly_payload()
        except Exception as exc:
            return {"status": "failed", "error": str(exc), "payload": payload}

    db.queue_sync_payload(
        course_id=payload["course_id"],
        week=payload["week"],
        payload_json=json.dumps(payload),
        payload_hash=payload["payload_hash"],
        last_error="university_server_url_not_configured",
    )
    db.write_sync_audit(payload["course_id"], payload["week"], len(payload["concepts"]), payload["payload_hash"], "queued", False)
    return {"status": "queued", "payload": payload}


@app.get("/api/concepts")
def get_concepts(student_id: str = "default", db=Depends(get_db)):
    rows = db.execute(
        """SELECT id, name, status, confidence, subject,
                  last_seen, created_at, cleared_at
           FROM concepts
           WHERE student_id=?
           ORDER BY
             CASE status
               WHEN 'persists' THEN 1
               WHEN 'on-loan'  THEN 2
               WHEN 'clear'    THEN 3
             END,
             created_at DESC""",
        [student_id],
    ).fetchall()
    return {"concepts": [dict(r) for r in rows]}


@app.get("/api/progress/summary")
def progress_summary(student_id: str = "default", db=Depends(get_db)):
    concepts = db.execute(
        "SELECT * FROM concepts WHERE student_id=?",
        [student_id],
    ).fetchall()

    total = len(concepts)
    on_loan = [c for c in concepts if c["status"] == "on-loan"]
    clear = [c for c in concepts if c["status"] == "clear"]
    persists = [c for c in concepts if c["status"] == "persists"]
    debt = round((len(on_loan) + len(persists)) / total * 100) if total > 0 else 0

    days_list = []
    for concept in clear:
        if concept["cleared_at"] and concept["created_at"]:
            try:
                d1 = datetime.fromisoformat(concept["created_at"])
                d2 = datetime.fromisoformat(concept["cleared_at"])
                days_list.append((d2 - d1).days)
            except Exception:
                pass
    avg_days = round(sum(days_list) / len(days_list), 1) if days_list else 0.0

    sessions = db.execute(
        """SELECT date(ended_at) as day
           FROM sessions
           WHERE student_id=? AND outcome='cleared'
           GROUP BY date(ended_at)
           ORDER BY day DESC""",
        [student_id],
    ).fetchall()
    streak = 0
    today = date.today()
    for i, row in enumerate(sessions):
        expected = (today - timedelta(days=i)).isoformat()
        if row["day"] == expected:
            streak += 1
        else:
            break

    concept_list = [
        {
            "name": c["name"],
            "confidence": c["confidence"] or 0.0,
            "status": c["status"],
        }
        for c in sorted(concepts, key=lambda x: x["confidence"] or 0, reverse=True)
    ]

    history = db.execute(
        """SELECT date(ended_at) as day,
                  COUNT(*) as cleared_count
           FROM sessions
           WHERE student_id=? AND outcome='cleared'
             AND ended_at >= date('now','-30 days')
           GROUP BY date(ended_at)
           ORDER BY day""",
        [student_id],
    ).fetchall()

    return {
        "debt_score": debt,
        "cleared_month": len(clear),
        "avg_days": avg_days,
        "streak": streak,
        "total": total,
        "on_loan": len(on_loan),
        "persists": len(persists),
        "concepts": concept_list,
        "debt_history": [dict(h) for h in history],
    }


@app.post("/api/scout")
def scout(body: dict, db=Depends(get_db)):
    content = (body.get("content") or "").strip()
    if not content:
        return {"concepts": []}

    base_url = body.get("ollama_url", DEFAULT_OLLAMA_URL)
    try:
        raw = ollama_client.chat(
            system=SCOUT_SYSTEM,
            user=f"Extract concepts from this study content:\n\n{content}",
            base_url=base_url,
            temperature=0.3,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        concepts = ollama_client.extract_json(raw)
        if not isinstance(concepts, list):
            concepts = list(concepts.values()) if isinstance(concepts, dict) else []
    except ValueError:
        concepts = [
            c.strip().strip('"').strip("'")
            for c in re.split(r"[\n,]", raw)
            if c.strip() and len(c.strip()) > 2
        ][:8]

    student_id = body.get("student_id", "default")
    session_id = body.get("session_id", str(uuid.uuid4()))
    inserted = []
    for concept in concepts[:8]:
        row = db.execute(
            """SELECT id, name, status, confidence, subject,
                      last_seen, created_at, cleared_at
               FROM concepts
               WHERE student_id=? AND lower(name)=lower(?)
               ORDER BY created_at DESC
               LIMIT 1""",
            [student_id, concept],
        ).fetchone()
        if row:
            db.execute(
                "UPDATE concepts SET last_seen=datetime('now') WHERE id=?",
                [row["id"]],
            )
            refreshed = dict(row)
            refreshed["last_seen"] = datetime.now().isoformat()
            inserted.append(refreshed)
            continue

        cid = str(uuid.uuid4())
        db.execute(
            """INSERT INTO concepts
               (id, student_id, name, status, confidence,
                created_at, last_seen)
               VALUES (?,?,?,'on-loan',0.0,datetime('now'),
               datetime('now'))""",
            [cid, student_id, concept],
        )
        row = db.execute(
            """SELECT id, name, status, confidence, subject,
                      last_seen, created_at, cleared_at
               FROM concepts
               WHERE id=?""",
            [cid],
        ).fetchone()
        if row:
            inserted.append(dict(row))
    db.commit()
    return {"concepts": inserted, "session_id": session_id}


@app.post("/api/sage")
def sage(body: dict, db=Depends(get_db)):
    concept = body.get("concept", "")
    history = body.get("history", [])
    student_msg = body.get("message", "")
    concept_id = body.get("concept_id", "")
    student_id = body.get("student_id", "default")
    base_url = body.get("ollama_url", DEFAULT_OLLAMA_URL)

    # ── Anti-gaming: score temporal fingerprint from the browser ─────────────
    temporal_fingerprint = body.get("temporal_fingerprint") or {}
    temporal_score = score_temporal_fingerprint(temporal_fingerprint)
    integrity_flag = temporal_score < 0.4  # suspicious if score too low

    history_text = "\n".join(
        f"{'Sage' if m['role'] == 'assistant' else 'Student'}: {m['content']}"
        for m in history[-6:]
    )

    system = SAGE_SYSTEM.format(
        concept=concept,
        history=history_text or "No prior exchanges yet.",
    )

    try:
        raw = ollama_client.chat(
            system=system,
            user=student_msg,
            base_url=base_url,
            temperature=0.8,
            max_tokens=150,  # Sage responses are capped at 50 words; 150 tokens is ample
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    cleared = False
    confidence = None
    try:
        result = ollama_client.extract_json(raw)
        if isinstance(result, dict) and result.get("verdict") == "CLEARED":
            # Only clear if the anti-gaming score doesn't flag serious cheating.
            # Score < 0.25 means paste + near-zero cadence variance; block the clear.
            if temporal_score >= 0.25:
                cleared = True
                confidence = result.get("confidence", 0.85)
                # Weight confidence down proportionally for borderline typing scores
                if temporal_score < 0.60:
                    confidence = round(confidence * temporal_score, 3)
                reply = "✓ You've demonstrated real understanding. This concept is now yours."
            else:
                reply = (
                    "Your answer looks like it may have been pasted rather than typed. "
                    "Please close this and try again in your own words, typed from scratch."
                )
        else:
            reply = raw
    except ValueError:
        reply = raw

    if cleared and concept_id:
        db.execute(
            """UPDATE concepts
               SET status='clear',
                   confidence=?,
                   cleared_at=datetime('now'),
                   last_seen=datetime('now')
               WHERE id=?""",
            [confidence, concept_id],
        )
        db.commit()
        db.execute(
            """INSERT INTO sessions
               (id, student_id, concept_id, concept_name,
                outcome, ended_at)
               VALUES (?,?,?,?,'cleared',datetime('now'))""",
            [str(uuid.uuid4()), student_id, concept_id, concept],
        )
        db.commit()

    return {
        "reply": reply,
        "cleared": cleared,
        "confidence": confidence,
        "temporal_score": round(temporal_score, 3),
        "integrity_flag": integrity_flag,
    }


@app.post("/api/lens")
async def lens(
    file: UploadFile = File(...),
    concept: str = Form(""),
    student_id: str = Form("default"),
    ollama_url: str = Form(DEFAULT_OLLAMA_URL),
    db=Depends(get_db),
):
    contents = await file.read()
    images_b64 = []

    if file.content_type == "application/pdf":
        try:
            import fitz
        except ModuleNotFoundError as exc:
            raise RuntimeError("PDF support requires pymupdf/fitz to be installed.") from exc
        doc = fitz.open(stream=contents, filetype="pdf")
        for i in range(min(len(doc), 3)):
            pix = doc[i].get_pixmap(dpi=150)
            images_b64.append(base64.b64encode(pix.tobytes("png")).decode())
    else:
        images_b64.append(base64.b64encode(contents).decode())

    concepts_row = db.execute(
        "SELECT name FROM concepts WHERE student_id=? AND status='on-loan' LIMIT 10",
        [student_id],
    ).fetchall()
    concept_list = [r["name"] for r in concepts_row]

    system = LENS_SYSTEM.format(concepts=json.dumps(concept_list))
    try:
        raw = ollama_client.chat(
            system=system,
            user=(
                "Analyze this student's handwritten work. "
                f"They say it's about: {concept or 'general study notes'}"
            ),
            base_url=ollama_url,
            images=[images_b64[0]],
            temperature=0.4,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        result = ollama_client.extract_json(raw)
    except ValueError:
        result = {
            "is_handwritten": True,
            "reasoning_quality": "partial",
            "concepts_found": [],
            "gaps": ["Could not fully analyze the image"],
            "feedback": "Image received. Try a clearer photo.",
            "recommendation": "Good lighting and full page visible.",
        }
    return result


@app.post("/api/solo")
def solo(body: dict):
    concept = body.get("concept", "")
    answer = body.get("answer", "")
    context = body.get("context", "")
    base_url = body.get("ollama_url", DEFAULT_OLLAMA_URL)

    system = SOLO_SYSTEM.format(
        concept=concept,
        context=context or "No additional context provided.",
    )
    try:
        raw = ollama_client.chat(
            system=system,
            user=f"Student's answer: {answer}",
            base_url=base_url,
            temperature=0.3,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        return ollama_client.extract_json(raw)
    except ValueError:
        return {
            "score": 0.5,
            "verdict": "PARTIAL",
            "what_was_right": "Could not evaluate",
            "what_was_missing": "Try again",
            "next_step": "Rephrase your answer more concisely",
        }


@app.get("/api/reports/student")
def reports_student(student_id: str = "default", db=Depends(get_db)):
    """Return all data needed for the student impact reports page."""
    concepts = db.execute(
        "SELECT * FROM concepts WHERE student_id=?", [student_id]
    ).fetchall()

    total = len(concepts)
    on_loan = [c for c in concepts if c["status"] == "on-loan"]
    clear = [c for c in concepts if c["status"] == "clear"]
    persists = [c for c in concepts if c["status"] == "persists"]
    debt_pct = round((len(on_loan) + len(persists)) / total * 100) if total > 0 else 0

    sessions = db.execute(
        """SELECT * FROM sessions WHERE student_id=?
           ORDER BY ended_at DESC""",
        [student_id],
    ).fetchall()
    cleared_sessions = [s for s in sessions if s["outcome"] == "cleared"]

    # Estimated Socratic tutoring time: avg 8 minutes per session
    tutoring_minutes = len(cleared_sessions) * 8

    # Streak
    streak = 0
    today = date.today()
    days_with_clears = db.execute(
        """SELECT date(ended_at) as day FROM sessions
           WHERE student_id=? AND outcome='cleared'
           GROUP BY date(ended_at) ORDER BY day DESC""",
        [student_id],
    ).fetchall()
    for i, row in enumerate(days_with_clears):
        expected = (today - timedelta(days=i)).isoformat()
        if row["day"] == expected:
            streak += 1
        else:
            break

    # Weekly history (last 4 weeks)
    weekly = db.execute(
        """SELECT strftime('%Y-W%W', ended_at) as week,
                  COUNT(*) as cleared
           FROM sessions
           WHERE student_id=? AND outcome='cleared'
             AND ended_at >= date('now','-28 days')
           GROUP BY week ORDER BY week""",
        [student_id],
    ).fetchall()

    # Subject breakdown
    subject_rows = db.execute(
        """SELECT subject, status, COUNT(*) as cnt
           FROM concepts WHERE student_id=?
           GROUP BY subject, status""",
        [student_id],
    ).fetchall()
    subjects: dict = {}
    for row in subject_rows:
        s = row["subject"] or "General"
        if s not in subjects:
            subjects[s] = {"on_loan": 0, "clear": 0, "persists": 0}
        subjects[s][row["status"].replace("-", "_")] = row["cnt"]

    # Avg days to clear
    days_list = []
    for c in clear:
        if c["cleared_at"] and c["created_at"]:
            try:
                d1 = datetime.fromisoformat(c["created_at"])
                d2 = datetime.fromisoformat(c["cleared_at"])
                days_list.append((d2 - d1).days)
            except Exception:
                pass
    avg_days_to_clear = round(sum(days_list) / len(days_list), 1) if days_list else 0

    return {
        "student_id": student_id,
        "total_concepts": total,
        "on_loan": len(on_loan),
        "cleared": len(clear),
        "persists": len(persists),
        "debt_pct": debt_pct,
        "tutoring_minutes": tutoring_minutes,
        "streak": streak,
        "avg_days_to_clear": avg_days_to_clear,
        "cleared_sessions": len(cleared_sessions),
        "weekly_history": [dict(r) for r in weekly],
        "subjects": subjects,
        "concepts": [
            {"name": c["name"], "status": c["status"], "confidence": c["confidence"] or 0}
            for c in sorted(concepts, key=lambda x: x["confidence"] or 0, reverse=True)
        ],
    }


@app.post("/api/sage/turn")
def sage_turn(body: dict):
    concept = (body.get("concept") or "").strip()
    student_id = (body.get("student_id") or "default").strip() or "default"
    session_id = (body.get("session_id") or "").strip() or f"sage-{uuid.uuid4().hex[:10]}"
    chat_history = body.get("chat_history") or []
    temporal_fingerprint = body.get("temporal_fingerprint") or {}

    temporal_score = score_temporal_fingerprint(temporal_fingerprint)
    db_session_id = db.get_or_create_learning_session(student_id, concept)
    db.update_comprehension_score(
        db_session_id,
        concept,
        {
            "temporal_score": temporal_score,
            "verification_signal": 0.0,
        },
    )

    result = orchestrator.trigger_clearing(
        concept,
        chat_history,
        session_id=session_id,
        student_id=student_id,
        db_session_id=db_session_id,
    )

    return {
        "session_id": session_id,
        "db_session_id": db_session_id,
        "concept": concept,
        "temporal_score": temporal_score,
        "cleared": result.cleared,
        "response": result.response,
    }
