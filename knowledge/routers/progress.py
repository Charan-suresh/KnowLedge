import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from .. import db

router = APIRouter()

@router.get("/progress", response_class=HTMLResponse)
async def get_progress(request: Request):
    progress_data = db.get_progress_over_time(30)
    clearing_velocity = db.get_clearing_velocity(14)
    subject_breakdown = db.get_subject_breakdown()
    concept_time_to_clear = db.get_concept_time_to_clear()
    
    # Extract curr_debt_score from progress_data (last item) and streak
    curr_debt_score = progress_data[-1]['debt_score'] if progress_data else 0
    prev_debt_score = progress_data[-8]['debt_score'] if len(progress_data) > 7 else curr_debt_score
    cleared_this_month = sum([d['cleared_count'] for d in clearing_velocity])
    numeric_days = [c["days_to_clear"] for c in concept_time_to_clear if isinstance(c.get("days_to_clear"), (int, float))]
    avg_days_to_clear = (sum(numeric_days) / len(numeric_days)) if numeric_days else 0
    
    # Weekly report mock just for streak
    weekly = db.get_weekly_report("demo")
    
    return request.app.state.templates.TemplateResponse(request, "progress.html", {
        "progress_data_json": json.dumps(progress_data),
        "clearing_velocity_json": json.dumps(clearing_velocity),
        "subject_breakdown_json": json.dumps(subject_breakdown),
        "concept_time_to_clear_json": json.dumps(concept_time_to_clear),
        "curr_debt_score": curr_debt_score,
        "prev_debt_score": prev_debt_score,
        "cleared_this_month": cleared_this_month,
        "avg_days_to_clear": round(avg_days_to_clear, 1),
        "streak_days": weekly['streak_days']
    })

@router.get("/progress/data", response_class=JSONResponse)
async def get_progress_data(days: int = 30):
    progress_data = db.get_progress_over_time(days)
    clearing_velocity = db.get_clearing_velocity(min(days, 14))
    return {"progress": progress_data, "velocity": clearing_velocity}
