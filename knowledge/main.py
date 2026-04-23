import json
import asyncio
import logging
import uuid
import base64
import httpx
import queue
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from pathlib import Path
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
from .agents.inference_router import check_health, get_health_status, chat_async
from .integrity.session_fingerprint import generate_device_key_if_missing
from .anti_gaming import score_temporal_fingerprint_with_breakdown, generate_probe

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent


def _log_startup_config_warnings() -> None:
    if not config.IS_PRODUCTION:
        return

    if config.INFERENCE_BACKEND == "ollama" and config.OLLAMA_BASE_URL == config.DEFAULT_OLLAMA_BASE_URL:
        logger.warning(
            "Production is configured for local Ollama at %s. Set INFERENCE_BACKEND=hf_space "
            "or provide a reachable remote OLLAMA_BASE_URL.",
            config.OLLAMA_BASE_URL,
        )

    if config.INFERENCE_BACKEND == "hf_space" and not config.HF_SPACE_URL:
        logger.error(
            "Production is configured for hf_space but HF_SPACE_URL is empty. "
            "Set HF_SPACE_URL to the deployed Hugging Face Space id or URL."
        )

    if config.INFERENCE_BACKEND != "ollama" and config.OLLAMA_BASE_URL == config.DEFAULT_OLLAMA_BASE_URL:
        logger.info(
            "Ollama embeddings are not configured in production; Chroma RAG will be skipped."
        )


def _base_context(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "is_production": config.IS_PRODUCTION,
        "demo_mode": config.DEMO_MODE,
        "inference_backend": config.INFERENCE_BACKEND,
    }
    if extra:
        payload.update(extra)
    return payload


async def warm_ollama() -> None:
    """Pull required models on Cloud Run if missing. Safe and idempotent."""
    if config.INFERENCE_BACKEND != "ollama":
        return

    models_needed = list({config.SCOUT_MODEL, config.SAGE_MODEL})
    headers = {"Authorization": f"Bearer {config.OLLAMA_AUTH_TOKEN}"} if config.OLLAMA_AUTH_TOKEN else {}

    for model in models_needed:
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                await client.post(
                    f"{config.OLLAMA_BASE_URL}/api/pull",
                    json={"name": model},
                    headers=headers,
                )
        except Exception as exc:
            logger.warning("[warm_ollama] Failed to pull %s: %s", model, exc)


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
    generate_device_key_if_missing()
    _log_startup_config_warnings()
    if config.DEMO_MODE:
        db.seed_demo_data_if_empty()
    config.load_runtime_llm_config(db.get_llm_settings())
    asyncio.create_task(warm_ollama())
    await _sweep_overdue_sessions()
    app_instance.state.sync_task = asyncio.create_task(_periodic_sync_worker())
    app_instance.state.orchestrator = orchestrator
    orchestrator.start_scout_loop()
    yield
    # ── Shutdown (nothing to clean up yet) ───────────────────────────────────
    task = getattr(app_instance.state, "sync_task", None)
    if task:
        task.cancel()


app = FastAPI(title="KnowLedge Backend", lifespan=lifespan)

# Mount static and templates
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.state.templates = templates  # share with routers via request.app.state
app.state.base_template_context = _base_context()

# Include routers
app.include_router(progress.router)
app.include_router(reports.router)
app.include_router(ingest_router)
app.include_router(classroom_router)

# Orchestrator (starts Scout background loop)
orchestrator = Orchestrator()

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
    student_id: str | None = None
    temporal_fingerprint: Dict[str, Any] | None = None


class ProbeRequest(BaseModel):
    session_id: str
    concept: str
    student_response: str
    difficulty: str = "medium"
    artifact_context: str | None = None


class SessionEventRequest(BaseModel):
    session_id: str
    concept: str
    event_type: str

class MarkOwnedRequest(BaseModel):
    concept: str


class LLMConfigRequest(BaseModel):
    ollama_base_url: str | None = None
    ollama_host: str | None = None
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
    return templates.TemplateResponse(request, "ledger.html", _base_context({
        "debts_json": json.dumps(debts),
        "heatmap_json": json.dumps(heatmap)
    }))

@app.get("/help", response_class=HTMLResponse)
async def read_help(request: Request):
    return templates.TemplateResponse(request, "help.html", _base_context())


@app.get("/health")
async def health():
    backend = await get_health_status()
    return {
        "status": "ok",
        "environment": config.ENVIRONMENT,
        "inference_backend": config.INFERENCE_BACKEND,
        "backend_reachable": backend.get("reachable", False),
        "backend_error": backend.get("error"),
        "backend_base_url": backend.get("base_url"),
        "backend_response": backend.get("response"),
        "hf_space_url": config.HF_SPACE_URL if config.INFERENCE_BACKEND == "hf_space" else None,
        "build_commit": config.BUILD_COMMIT or None,
        "build_branch": config.BUILD_BRANCH or None,
        "render_service_name": config.RENDER_SERVICE_NAME or None,
    }


@app.get("/api/warmup")
async def warmup():
    """Fire-and-forget warmup endpoint to reduce first-judge latency."""
    asyncio.create_task(check_health())
    return {"status": "warming"}


# ── Agent API Endpoints ───────────────────────────────────────────────────────

@app.get("/api/state")
async def get_state():
    debts = db.get_all_active_debt(include_legacy=False)
    heatmap = db.get_class_heatmap(include_legacy=False)
    return {"debts": debts, "heatmap": heatmap}


@app.get("/api/events")
async def get_events(limit: int = Query(50, ge=1, le=500)):
    events = []
    while len(events) < limit:
        try:
            events.append(orchestrator.event_bus.get_nowait())
        except queue.Empty:
            break
    return events


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
    models = config.fetch_ollama_models(runtime["ollama_base_url"]) if config.INFERENCE_BACKEND == "ollama" else []
    return {
        **runtime,
        "available_models": models
    }


@app.get("/api/llm/models")
async def get_llm_models(host: str = Query(None)):
    target_host = host or config.OLLAMA_BASE_URL
    models = config.fetch_ollama_models(target_host)
    return {"host": target_host, "models": models}


@app.post("/api/llm/config")
async def update_llm_config(req: LLMConfigRequest):
    base_url = (req.ollama_base_url or req.ollama_host or "").strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="Ollama host is required")
    if not req.scout_model.strip() or not req.sage_model.strip() or not req.lens_model.strip():
        raise HTTPException(status_code=400, detail="All model fields are required")

    updated = config.set_runtime_llm_config(
        ollama_base_url=base_url,
        scout_model=req.scout_model,
        sage_model=req.sage_model,
        lens_model=req.lens_model,
    )
    db.save_llm_settings(
        ollama_base_url=updated["ollama_base_url"],
        scout_model=updated["scout_model"],
        sage_model=updated["sage_model"],
        lens_model=updated["lens_model"],
    )
    models = config.fetch_ollama_models(updated["ollama_base_url"])
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
    inserted_concepts: list[str] = []
    seen = set()
    for concept in concepts:
        concept_name = (concept.concept_tag or "").strip()
        if not concept_name:
            continue
        key = concept_name.lower()
        if key in seen:
            continue
        seen.add(key)

        confidence = float(max(0.0, min(1.0, concept.confidence_score)))
        db.insert_debt(concept_name, req.text, confidence)
        orchestrator.event_bus.put({"type": "DEBT_ADDED", "concept": concept_name})
        inserted += 1
        inserted_concepts.append(concept_name)
    return {"status": "ok", "inserted": inserted, "concepts": inserted_concepts}

@app.post("/api/sage/turn")
async def trigger_sage(req: SageRequest):
    """Synchronous Sage turn — used by the standalone dashboard modal."""
    try:
        concept = (req.concept or "").strip()
        if not concept:
            raise HTTPException(status_code=400, detail="Concept is required")

        student_id = (req.student_id or "anonymous").strip() or "anonymous"
        db_session_id = db.get_or_create_learning_session(student_id, concept)
        if req.session_id:
            db.set_session_alias(req.session_id, db_session_id)

        if req.temporal_fingerprint:
            temporal_breakdown = score_temporal_fingerprint_with_breakdown(req.temporal_fingerprint)
            temporal_score = float(temporal_breakdown["score"])
            db.update_comprehension_score(
                session_id=db_session_id,
                concept=concept,
                new_signal={"temporal_score": temporal_score},
            )
            db.log_audit_event(
                event_type="temporal_score",
                session_id=str(db_session_id),
                student_id=student_id,
                concept=concept,
                inputs=req.temporal_fingerprint,
                decision=temporal_breakdown,
            )

        pending_traps = db.get_pending_wrong_traps(str(db_session_id), concept)
        latest_student_text = ""
        for msg in reversed(req.chat_history):
            if (msg.get("role") or "").lower() in {"user", "student"}:
                latest_student_text = (msg.get("content") or "").strip().lower()
                break

        if pending_traps and latest_student_text:
            agreed = any(token in latest_student_text for token in ("yes", "correct", "right", "exactly"))
            corrected = any(token in latest_student_text for token in ("no", "not", "incorrect", "actually", "instead"))
            trap_score = 0.0 if agreed and not corrected else 1.0
            for trap in pending_traps:
                db.resolve_probe(trap["id"], student_corrected=(trap_score >= 0.99))
            db.update_comprehension_score(
                session_id=db_session_id,
                concept=concept,
                new_signal={"trap_score": trap_score},
            )
            db.log_audit_event(
                event_type="wrong_trap_resolution",
                session_id=str(db_session_id),
                student_id=student_id,
                concept=concept,
                inputs={"latest_student_text": latest_student_text, "pending_traps": len(pending_traps)},
                decision={"trap_score": trap_score},
            )

        result = orchestrator.trigger_clearing(
            concept,
            req.chat_history,
            session_id=req.session_id,
            student_id=student_id,
            db_session_id=db_session_id,
        )
        direct_answer_score = 0.85 if result.cleared else 0.45
        probe_depth_score = min(1.0, max(0.1, len(req.chat_history) / 4.0))
        comprehension = db.update_comprehension_score(
            session_id=db_session_id,
            concept=concept,
            new_signal={
                "direct_answer_score": direct_answer_score,
                "probe_depth_score": probe_depth_score,
            },
        )
        db.log_audit_event(
            event_type="comprehension_update",
            session_id=str(db_session_id),
            student_id=student_id,
            concept=concept,
            inputs={"direct_answer_score": direct_answer_score, "probe_depth_score": probe_depth_score},
            decision=comprehension,
        )
        return {"cleared": result.cleared, "response": result.response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sage/probe")
async def create_probe(req: ProbeRequest):
    probe_data = generate_probe(
        student_response=req.student_response,
        concept=req.concept,
        artifact_context=req.artifact_context,
        difficulty=req.difficulty,
    )
    probe_id = db.register_probe(req.session_id, req.concept, probe_data["strategy"], probe_data["probe"])
    db.log_audit_event(
        event_type="probe_generated",
        session_id=req.session_id,
        student_id=None,
        concept=req.concept,
        inputs={
            "difficulty": req.difficulty,
            "artifact_context": bool(req.artifact_context),
            "student_response_length": len(req.student_response or ""),
        },
        decision={"probe_id": probe_id, "strategy": probe_data["strategy"], "probe": probe_data["probe"]},
    )
    return {"probe": probe_data["probe"], "strategy": probe_data["strategy"], "probe_id": probe_id}


@app.post("/api/sage/session-event")
async def record_sage_session_event(req: SessionEventRequest):
    event = (req.event_type or "").strip().lower()
    session_id = (req.session_id or "").strip()
    concept = (req.concept or "").strip()
    if not session_id or not concept:
        raise HTTPException(status_code=400, detail="session_id and concept are required")

    penalized = 0
    if event == "close":
        resolved_session_id = session_id
        if not session_id.isdigit():
            alias = db.get_db_session_id_from_alias(session_id)
            if alias is not None:
                resolved_session_id = str(alias)
        penalized = db.penalize_open_interrupts_for_session(resolved_session_id)

    db.log_audit_event(
        event_type="session_event",
        session_id=session_id,
        student_id=None,
        concept=concept,
        inputs={"event_type": event},
        decision={"penalized_interrupts": penalized},
    )
    return {"status": "ok", "penalized_interrupts": penalized}


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
            "explanation": result.explanation,
            "handwritten": result.handwritten,
            "has_issue": result.has_issue,
            "confidence": result.confidence,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/verify-diagram")
async def verify_diagram(
    image: UploadFile = File(...),
    concept: str = Form(...),
    expected_elements: List[str] = Form(...),
):
    raw_elements: List[str] = expected_elements or []
    if len(raw_elements) == 1:
        candidate = (raw_elements[0] or "").strip()
        if candidate.startswith("[") and candidate.endswith("]"):
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, list):
                    raw_elements = [str(x) for x in parsed]
            except Exception:
                pass

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image is empty")

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    expected_text = ", ".join(raw_elements)
    prompt = (
        "You are verifying a student-submitted diagram photo. Return strict JSON with keys: "
        "verified (bool), elements_found (array of strings), is_likely_handwritten (bool), confidence (0..1). "
        "Assess whether this looks hand-drawn on paper (imperfect lines, shadows, texture) and not a clean digital screenshot. "
        "If it looks digital, set is_likely_handwritten=false and reduce confidence. "
        f"Concept: {concept}. Expected elements: {expected_text}."
    )

    model_response = await chat_async(
        model=config.LENS_MODEL,
        messages=[
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
                "images": [image_b64],
            }
        ],
        format="json",
    )
    content = (model_response.get("message", {}) or {}).get("content", "")

    try:
        parsed = json.loads(content)
    except Exception:
        parsed = {
            "verified": False,
            "elements_found": [],
            "is_likely_handwritten": False,
            "confidence": 0.2,
        }

    verified = bool(parsed.get("verified", False))
    elements_found = parsed.get("elements_found", []) or []
    is_likely_handwritten = bool(parsed.get("is_likely_handwritten", False))
    confidence = float(parsed.get("confidence", 0.0) or 0.0)
    confidence = max(0.0, min(1.0, confidence))
    if not is_likely_handwritten:
        confidence = min(confidence, 0.35)
        verified = False

    db_session_id = db.get_or_create_learning_session("anonymous", concept.strip())
    comprehension = db.update_comprehension_score(
        session_id=db_session_id,
        concept=concept.strip(),
        new_signal={"verification_signal": confidence if verified else 0.0},
    )
    db.log_audit_event(
        event_type="diagram_verification",
        session_id=str(db_session_id),
        student_id="anonymous",
        concept=concept.strip(),
        inputs={"expected_elements": raw_elements},
        decision={
            "verified": verified,
            "elements_found": elements_found,
            "is_likely_handwritten": is_likely_handwritten,
            "confidence": confidence,
            "comprehension_status": comprehension.get("status"),
        },
    )

    return {
        "verified": verified,
        "elements_found": elements_found,
        "is_likely_handwritten": is_likely_handwritten,
        "confidence": confidence,
    }


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


@app.get("/api/comprehension/debt-report")
async def comprehension_debt_report(student_id: str = Query(...)):
    value = (student_id or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="student_id is required")
    return {
        "student_id": value,
        "grouped_concepts": db.get_student_debt_report(value),
    }


@app.get("/api/report/before-after")
async def report_before_after(concept: str = Query(...)):
    if not concept.strip():
        raise HTTPException(status_code=400, detail="concept is required")
    return db.get_before_after(concept.strip())
