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

from fastapi import Depends, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import ollama_client
from .init_db import DB_PATH, init
from .prompts import LENS_SYSTEM, SAGE_SYSTEM, SCOUT_SYSTEM, SOLO_SYSTEM
from .seed_demo import seed

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"


def init_app() -> None:
    init()
    if DEMO_MODE:
        seed("demo")


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
    return (request.cookies.get("student_id") or "default").strip() or "default"


def render_page(request: Request, template_name: str, extra: dict | None = None):
    context = {
        "request": request,
        "demo_mode": DEMO_MODE,
        "default_ollama_url": DEFAULT_OLLAMA_URL,
        "student_id": get_student_id(request),
    }
    if extra:
        context.update(extra)
    return templates.TemplateResponse(request, template_name, context)


@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url="/ledger")


@app.get("/ledger", response_class=HTMLResponse)
def ledger_page(request: Request):
    return render_page(request, "ledger.html")


@app.get("/progress", response_class=HTMLResponse)
def progress_page(request: Request):
    return render_page(request, "progress.html")


@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request):
    return render_page(request, "reports.html")


@app.get("/help", response_class=HTMLResponse)
def help_page(request: Request):
    return render_page(request, "help.html")


@app.get("/demo")
def demo_route():
    seed("demo")
    response = RedirectResponse(url="/ledger")
    response.set_cookie("student_id", "demo", samesite="lax")
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def status(ollama_url: str = Query(DEFAULT_OLLAMA_URL)):
    return ollama_client.is_ready(ollama_url)


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
    raw = ollama_client.chat(
        system=SCOUT_SYSTEM,
        user=f"Extract concepts from this study content:\n\n{content}",
        base_url=base_url,
        temperature=0.3,
    )

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

    history_text = "\n".join(
        f"{'Sage' if m['role'] == 'assistant' else 'Student'}: {m['content']}"
        for m in history[-6:]
    )

    system = SAGE_SYSTEM.format(
        concept=concept,
        history=history_text or "No prior exchanges yet.",
    )

    raw = ollama_client.chat(
        system=system,
        user=student_msg,
        base_url=base_url,
        temperature=0.8,
    )

    cleared = False
    confidence = None
    try:
        result = ollama_client.extract_json(raw)
        if isinstance(result, dict) and result.get("verdict") == "CLEARED":
            cleared = True
            confidence = result.get("confidence", 0.85)
            reply = "✓ You've demonstrated real understanding. This concept is now yours."
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

    return {"reply": reply, "cleared": cleared, "confidence": confidence}


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
    raw = ollama_client.chat(
        system=system,
        user=f"Student's answer: {answer}",
        base_url=base_url,
        temperature=0.3,
    )

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
