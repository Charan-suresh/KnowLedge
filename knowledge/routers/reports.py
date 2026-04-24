from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
import io
import csv
from .. import db
from .. import config
from ..agents.inference_router import chat

router = APIRouter()

@router.get("/reports", response_class=HTMLResponse)
async def get_reports(request: Request, view: str = "student"):
    weekly_report = db.get_weekly_report("demo")
    class_report = db.get_class_report_data()
    concept_time_to_clear = db.get_concept_time_to_clear()
    integrity_summary = db.get_integrity_summary()
    sync_audit = db.get_sync_audit_log()[:10]
    
    context = {
        **request.app.state.base_template_context,
        "view": view,
        "weekly_report": weekly_report,
        "class_report": class_report,
        "concept_time_to_clear": concept_time_to_clear,
        "integrity_summary": integrity_summary,
        "sync_audit": sync_audit,
    }
    return request.app.state.templates.TemplateResponse(request, "reports.html", context)

@router.get("/reports/export")
async def export_reports(format: str = "csv"):
    class_report = db.get_class_report_data()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Concept", "Total Borrowed", "Total Cleared", "Avg Days to Clear", "Persistence Rate (%)"])
    for row in class_report:
        writer.writerow([
            row["concept"], 
            row["total_borrowed"], 
            row["total_cleared"], 
            row["avg_days_to_clear"], 
            row["persistence_rate"]
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), 
        media_type="text/csv", 
        headers={"Content-Disposition": "attachment; filename=class_report.csv"}
    )


def _recommend_for_concept(concept: str, score: float) -> str:
    prompt = (
        "You are Sage. Generate one short study recommendation (max 14 words). "
        "No bullet points, no numbering, no preamble. "
        f"Concept: {concept}. Current comprehension score: {score:.2f}."
    )
    try:
        response = chat(
            model=config.SAGE_MODEL,
            messages=[
                {"role": "system", "content": "Return one concise recommendation sentence only."},
                {"role": "user", "content": prompt},
            ],
        )
        text = (response.get("message", {}) or {}).get("content", "").strip()
        return text or f"Review {concept} with one worked example and one edge case."
    except Exception:
        return f"Review {concept} with one worked example and one edge case."


@router.get("/reports/{student_id}")
async def get_student_report(student_id: str):
    value = (student_id or "").strip()
    if not value:
        return {
            "student_id": "",
            "per_concept": [],
            "comprehension_debt": [],
            "temporal_anomaly_count": 0,
            "recommended_actions": [],
            "session_history": [],
        }

    snapshot = db.get_student_report_data(value)
    debt = snapshot.get("debt_concepts", [])
    recommendations = [
        {
            "concept": row["concept"],
            "recommendation": _recommend_for_concept(row["concept"], float(row["comprehension_score"])),
        }
        for row in debt
    ]

    return {
        "student_id": value,
        "per_concept": snapshot.get("per_concept", []),
        "comprehension_debt": debt,
        "temporal_anomaly_count": snapshot.get("temporal_anomaly_count", 0),
        "recommended_actions": recommendations,
        "session_history": snapshot.get("session_history", []),
    }
