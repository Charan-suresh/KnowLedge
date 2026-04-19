from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
import io
import csv
from .. import db

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
