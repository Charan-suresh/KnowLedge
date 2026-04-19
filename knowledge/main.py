import json
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict, Any

from . import db
from . import config
from . import classroom_client
from .orchestrator import Orchestrator
from .scout import tag_content
from .sage_stream import run_sage_ollama
from .prompt_engineering import generate_solo_question
from .sync.sender import send_weekly_payload, retry_pending_sync
from .sync.audit_log import get_sync_audit
from .routers import progress, reports
from .routers.ingest import router as ingest_router
from .routers.classroom import router as classroom_router

logger = logging.getLogger(__name__)


async def _periodic_sync_worker():
    while True:
        try:
            send_weekly_payload()
            retry_pending_sync()
        except Exception as e:
            logger.error("[sync] periodic sync failed: %s", e)
        await asyncio.sleep(6 * 60 * 60)


async def _sweep_overdue_sessions():
    """
    Startup sweep: any sessions that passed their 24-hour deadline while the
    server was offline are force-unlocked immediately. Pending sessions that
    are still within their window get a new asyncio task for the remaining time.
    """
    overdue = db.get_pending_sessions_past_deadline()
    for session in overdue:
        logger.info(f"[startup_sweep] Auto-submitting overdue session {session['session_id']}")
        if session.get("course_id") and session.get("attachment_id") and session.get("submission_id"):
            try:
                await classroom_client.patch_submission_state(
                    course_id=session["course_id"],
                    coursework_id=session["assignment_id"],
                    attachment_id=session["attachment_id"],
                    submission_id=session["submission_id"],
                    student_id=session["student_id"],
                    state=classroom_client.STATE_TURNED_IN,
                )
            except Exception as e:
                logger.error(f"[startup_sweep] Classroom API error for {session['session_id']}: {e}")
        db.update_session_status(session["session_id"], "auto_submitted")

    logger.info(f"[startup_sweep] Processed {len(overdue)} overdue session(s).")


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    db.init_db()
    db.run_migrations()
    config.load_runtime_llm_config(db.get_llm_settings())
    await _sweep_overdue_sessions()
    app_instance.state.sync_task = asyncio.create_task(_periodic_sync_worker())
    yield
    # ── Shutdown (nothing to clean up yet) ───────────────────────────────────
    task = getattr(app_instance.state, "sync_task", None)
    if task:
        task.cancel()


app = FastAPI(title="KnowLedge Backend", lifespan=lifespan)

# Mount static and templates
app.mount("/static", StaticFiles(directory="knowledge/static"), name="static")
templates = Jinja2Templates(directory="knowledge/templates")
app.state.templates = templates  # share with routers via request.app.state

# Include routers
app.include_router(progress.router)
app.include_router(reports.router)
app.include_router(ingest_router)
app.include_router(classroom_router)

# Orchestrator (starts Scout background loop)
orchestrator = Orchestrator()
orchestrator.start_scout_loop()

# Ensure schema exists even when app lifespan isn't entered (e.g., raw TestClient usage).
db.init_db()
db.run_migrations()


# ── Pydantic models ───────────────────────────────────────────────────────────

class ScoutRequest(BaseModel):
    text: str

class SageRequest(BaseModel):
    concept: str
    chat_history: List[Dict[str, str]]
    session_id: str | None = None

class MarkOwnedRequest(BaseModel):
    concept: str


class LLMConfigRequest(BaseModel):
    ollama_host: str
    scout_model: str
    sage_model: str
    lens_model: str


class SoloStartRequest(BaseModel):
    concept: str


class SoloEvaluateRequest(BaseModel):
    concept: str
    session_id: str
    response: str


# ── Page Routes ───────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return RedirectResponse(url="/ledger")

@app.get("/ledger", response_class=HTMLResponse)
async def read_ledger(request: Request):
    debts = db.get_all_active_debt(include_legacy=False)
    heatmap = db.get_class_heatmap(include_legacy=False)
    return templates.TemplateResponse(request, "ledger.html", {
        "debts_json": json.dumps(debts),
        "heatmap_json": json.dumps(heatmap)
    })

@app.get("/help", response_class=HTMLResponse)
async def read_help(request: Request):
    return templates.TemplateResponse(request, "help.html", {})


# ── Agent API Endpoints ───────────────────────────────────────────────────────

@app.get("/api/state")
async def get_state():
    debts = db.get_all_active_debt(include_legacy=False)
    heatmap = db.get_class_heatmap(include_legacy=False)
    return {"debts": debts, "heatmap": heatmap}


@app.get("/api/debt-score")
async def get_debt_score():
    """
    Computes the live debt score:
      score = (on_loan + persists) / total_active * 100
    Returns 0 when no debt entries exist.
    """
    debts = db.get_all_active_debt(include_legacy=False)
    total = len(debts)
    if total == 0:
        return {"score": 0, "on_loan": 0, "persists": 0, "clear": 0, "total": 0}
    active = sum(1 for d in debts if d["status"] in ("on_loan", "persists"))
    clear  = sum(1 for d in debts if d["status"] in ("clear", "owned"))
    score  = round(active / total * 100)
    return {"score": score, "on_loan": sum(1 for d in debts if d["status"] == "on_loan"),
            "persists": sum(1 for d in debts if d["status"] == "persists"),
            "clear": clear, "total": total}


@app.get("/api/llm/config")
async def get_llm_config():
    runtime = config.get_runtime_llm_config()
    models = config.fetch_ollama_models(runtime["ollama_host"])
    return {
        **runtime,
        "available_models": models
    }


@app.get("/api/llm/models")
async def get_llm_models(host: str = Query(None)):
    target_host = host or config.OLLAMA_HOST
    models = config.fetch_ollama_models(target_host)
    return {"host": target_host, "models": models}


@app.post("/api/llm/config")
async def update_llm_config(req: LLMConfigRequest):
    if not req.ollama_host.strip():
        raise HTTPException(status_code=400, detail="Ollama host is required")
    if not req.scout_model.strip() or not req.sage_model.strip() or not req.lens_model.strip():
        raise HTTPException(status_code=400, detail="All model fields are required")

    updated = config.set_runtime_llm_config(
        ollama_host=req.ollama_host,
        scout_model=req.scout_model,
        sage_model=req.sage_model,
        lens_model=req.lens_model,
    )
    db.save_llm_settings(
        ollama_host=updated["ollama_host"],
        scout_model=updated["scout_model"],
        sage_model=updated["sage_model"],
        lens_model=updated["lens_model"],
    )
    models = config.fetch_ollama_models(updated["ollama_host"])
    return {
        "status": "ok",
        **updated,
        "available_models": models
    }

@app.post("/api/scout")
async def trigger_scout(req: ScoutRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    # Process inline so UI refresh sees updates immediately.
    concepts = tag_content(req.text)
    inserted = 0
    for concept in concepts:
        db.insert_debt(concept.concept_tag, req.text, concept.confidence_score)
        orchestrator.event_bus.put({"type": "DEBT_ADDED", "concept": concept.concept_tag})
        inserted += 1
    return {"status": "ok", "inserted": inserted}

@app.post("/api/sage/turn")
async def trigger_sage(req: SageRequest):
    """Synchronous Sage turn — used by the standalone dashboard modal."""
    try:
        result = orchestrator.trigger_clearing(req.concept, req.chat_history, session_id=req.session_id)
        return {"cleared": result.cleared, "response": result.response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sage/start-solo")
async def start_solo(req: SoloStartRequest):
    concept = (req.concept or "").strip()
    if not concept:
        raise HTTPException(status_code=400, detail="Concept is required")

    prior = db.get_prior_solo_questions(concept)
    question = generate_solo_question(concept, prior)
    session_id = f"solo-{uuid.uuid4().hex[:10]}"
    started_at = datetime.utcnow()
    expires_at = started_at + timedelta(seconds=config.SOLO_TIMEOUT_SECONDS)
    db.create_solo_session(
        session_id=session_id,
        concept=concept,
        question=question,
        started_at=started_at.isoformat(),
        expires_at=expires_at.isoformat(),
    )
    return {
        "session_id": session_id,
        "concept": concept,
        "question": question,
        "expires_at": expires_at.isoformat(),
    }


@app.post("/api/sage/solo-evaluate")
async def solo_evaluate(req: SoloEvaluateRequest):
    concept = (req.concept or "").strip()
    if not concept:
        raise HTTPException(status_code=400, detail="Concept is required")
    if not req.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required")
    if not req.response.strip():
        raise HTTPException(status_code=400, detail="response is required")

    result = orchestrator.trigger_solo_mode(concept, req.response, req.session_id)
    return result

@app.post("/api/sage/mark-owned")
async def mark_sage_owned(req: MarkOwnedRequest):
    concept = (req.concept or "").strip()
    if not concept:
        raise HTTPException(status_code=400, detail="Empty concept")
    updated = db.update_status(concept, "clear")
    return {"status": "ok", "updated": updated}

@app.get("/api/sage/stream")
async def sage_stream_endpoint(
    request: Request,
    session_id: str = Query(...),
    history: str = Query("[]"),
    concept: str = Query(None),  # optional: passed directly from ledger modal
):
    """
    SSE streaming endpoint for both:
      - Ledger modal (concept passed as query param)
      - Classroom iframe (concept resolved from classroom_session via session_id)

    Streams Sage tokens as `data: {"token": "..."}` events.
    Sage is grounded via RAG against the US Curriculum Guide vectorstore.
    Sends `data: {"status": "cleared"}` or `data: {"status": "complete"}` at end.
    """
    try:
        chat_history = json.loads(history)
    except Exception:
        chat_history = []

    async def event_generator():
        cleared = False
        async for token in run_sage_ollama(session_id, chat_history, concept=concept):
            if await request.is_disconnected():
                break
            if token == "\n__CLEARED__":
                cleared = True
                continue
            yield f"data: {json.dumps({'token': token})}\n\n"
        if cleared:
            yield f"data: {json.dumps({'status': 'cleared'})}\n\n"
        else:
            yield f"data: {json.dumps({'status': 'complete'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

@app.post("/api/lens/verify")
async def trigger_lens(concept: str = Form(...), file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        result = orchestrator.trigger_lens_check(image_bytes, concept)
        return {
            "x": result.x, "y": result.y,
            "width": result.width, "height": result.height,
            "explanation": result.explanation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync/share-weekly")
async def sync_share_weekly():
    return send_weekly_payload()


@app.post("/api/sync/retry-pending")
async def sync_retry_pending():
    return retry_pending_sync()


@app.get("/api/sync/status")
async def sync_status():
    audit = get_sync_audit()
    pending = db.get_pending_sync_payloads()
    last = audit[0] if audit else None
    return {
        "enabled": True,
        "course_id": config.COURSE_ID,
        "last_sync": last,
        "pending_count": len(pending),
        "wifi_only": config.SYNC_ON_WIFI_ONLY,
    }


@app.get("/api/sync/audit")
async def sync_audit():
    return {"rows": get_sync_audit()}


@app.get("/api/integrity/report")
async def integrity_report():
    return db.get_integrity_summary()


@app.get("/api/report/before-after")
async def report_before_after(concept: str = Query(...)):
    if not concept.strip():
        raise HTTPException(status_code=400, detail="concept is required")
    return db.get_before_after(concept.strip())
