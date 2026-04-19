"""
routers/ingest.py
Handles student content submission from the Classroom iframe.
Runs Scout in-process, schedules the 24-hour auto-submit safety valve.
"""

import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .. import db
from ..scout import tag_content
from .. import classroom_client
from .. import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


class IngestRequest(BaseModel):
    content: str
    student_id: str
    assignment_id: str   # treated as concept name for now; maps to Classroom coursework ID
    course_id: str = ""
    attachment_id: str = ""
    submission_id: str = ""


class IngestResponse(BaseModel):
    session_id: str
    debt_found: bool
    concepts: list[str]


@router.post("/ingest", response_model=IngestResponse)
async def ingest_content(req: IngestRequest, background_tasks: BackgroundTasks):
    """
    1. Run Scout synchronously to extract concepts from student content.
    2. Persist concepts to debt_log.
    3. Create a classroom_session record.
    4. Schedule the 24-hour auto-submit safety valve.
    5. Return session_id and whether debt was found.
    """
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Empty content")

    # 1. Scout runs synchronously here (fast E2B model)
    try:
        tags = tag_content(req.content)
    except Exception as e:
        logger.error(f"Scout failed: {e}")
        tags = []

    concepts = [t.concept_tag for t in tags]
    debt_found = len(concepts) > 0

    # 2. Persist to debt_log
    for tag in tags:
        db.insert_debt(tag.concept_tag, req.content, tag.confidence_score)

    # 3. Create Classroom session record
    session_id = str(uuid.uuid4())
    deadline = (datetime.now(timezone.utc) + timedelta(hours=config.AUTO_SUBMIT_HOURS)).isoformat()

    db.create_classroom_session(
        session_id=session_id,
        student_id=req.student_id,
        assignment_id=req.assignment_id,
        course_id=req.course_id,
        deadline_at=deadline,
    )

    # Store attachment/submission IDs if provided at intake
    if req.attachment_id and req.submission_id:
        db.update_session_status(
            session_id, "debt_found" if debt_found else "no_debt",
            attachment_id=req.attachment_id,
            submission_id=req.submission_id,
        )

    # 4. Schedule 24h auto-submit safety valve
    background_tasks.add_task(
        auto_submit_after_deadline,
        session_id=session_id,
        delay_hours=config.AUTO_SUBMIT_HOURS,
    )

    # 5. If no debt found, immediately unlock Turn In
    if not debt_found and req.course_id and req.attachment_id and req.submission_id:
        try:
            await classroom_client.patch_submission_state(
                course_id=req.course_id,
                coursework_id=req.assignment_id,
                attachment_id=req.attachment_id,
                submission_id=req.submission_id,
                student_id=req.student_id,
                state=classroom_client.STATE_TURNED_IN,
            )
            db.update_session_status(session_id, "cleared")
        except Exception as e:
            logger.warning(f"Could not auto-unlock (no debt): {e}")

    return IngestResponse(
        session_id=session_id,
        debt_found=debt_found,
        concepts=concepts,
    )


async def auto_submit_after_deadline(session_id: str, delay_hours: int):
    """
    Safety valve: waits `delay_hours`, then force-unlocks Turn In if the
    student hasn't completed Sage. No student ever loses their submission.
    """
    await asyncio.sleep(delay_hours * 3600)

    session = db.get_classroom_session(session_id)
    if not session:
        return

    if session["status"] in ("cleared", "auto_submitted"):
        logger.info(f"[auto_submit] {session_id} already resolved, skipping.")
        return

    logger.info(f"[auto_submit] Deadline passed for {session_id}. Force-unlocking Turn In.")

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
            logger.error(f"[auto_submit] Classroom API call failed: {e}")

    db.update_session_status(session_id, "auto_submitted")
