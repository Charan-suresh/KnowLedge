import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from .. import db

router = APIRouter()

@router.get("/progress", response_class=HTMLResponse)
async def get_progress(request: Request):
    summary = db.get_progress_summary("demo")
    history = db.get_progress_history(30)
    concept_rows = db.get_progress_concepts("demo")
    
    context = {
        **request.app.state.base_template_context,
        "progress_summary_json": json.dumps(summary),
        "progress_history_json": json.dumps(history),
        "concept_rows_json": json.dumps(concept_rows),
        "curr_debt_score": summary.get("debt_score", 0),
        "prev_debt_score": summary.get("debt_score", 0),
        "cleared_this_month": summary.get("cleared_this_month", 0),
        "avg_days_to_clear": summary.get("avg_days_to_clear", 0),
        "streak_days": summary.get("streak", 0),
    }
    return request.app.state.templates.TemplateResponse(request, "progress.html", context)

@router.get("/progress/data", response_class=JSONResponse)
async def get_progress_data(days: int = 30):
    history = db.get_progress_history(days)
    return {
        "progress": history.get("scores", []),
        "velocity": history.get("cleared", []),
        "dates": history.get("dates", []),
    }


@router.get("/api/progress/summary", response_class=JSONResponse)
async def get_progress_summary(student_id: str = "demo"):
    return db.get_progress_summary(student_id)


@router.get("/api/progress/debt-history", response_class=JSONResponse)
async def get_progress_debt_history(student_id: str = "demo"):
    return db.get_progress_history(14)


@router.get("/api/progress/concepts", response_class=JSONResponse)
async def get_progress_concepts(student_id: str = "demo"):
    return {"concepts": db.get_progress_concepts(student_id)}


@router.get("/progress/{student_id}", response_class=JSONResponse)
async def get_student_progress(student_id: str):
    value = (student_id or "").strip()
    if not value:
        return {
            "concepts": [],
            "overall_score": 0.0,
            "debt_concepts": [],
            "verified_concepts": [],
        }
    data = db.get_student_progress_overview(value)
    return {
        "concepts": data.get("concepts", []),
        "overall_score": data.get("overall_score", 0.0),
        "debt_concepts": data.get("debt_concepts", []),
        "verified_concepts": data.get("verified_concepts", []),
    }
