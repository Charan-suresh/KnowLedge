"""
routers/classroom.py
Serves the Google Classroom Add-on views (teacher, student iframe, review)
and handles the OAuth callback + attachment unlock flow.

Routes
------
POST /classroom/attach          — Teacher webhook: create attachment on an assignment
GET  /classroom/auth/login      — Student OAuth redirect
GET  /classroom/auth/callback   — Student OAuth exchange
GET  /classroom/teacher-view    — Teacher iframe (configuration)
GET  /classroom/student-view    — Student iframe (Sage verification)
GET  /classroom/review          — Student work review URI
POST /classroom/unlock/{id}     — Called when Sage clears all debt
"""

import json
import logging
import urllib.parse
from fastapi import APIRouter, Request, HTTPException, Query, Header
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from .. import db, config
from .. import classroom_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/classroom")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

# Scopes used by students (read submission state)
STUDENT_SCOPES = " ".join([
    "https://www.googleapis.com/auth/classroom.addons.student",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "openid", "email", "profile",
])

# Scopes used by teachers (create/manage attachments)
TEACHER_SCOPES = " ".join([
    "https://www.googleapis.com/auth/classroom.addons.teacher",
    "openid", "email", "profile",
])

# ── Teacher Attachment Webhook ────────────────────────────────────────────────

class AttachRequest(BaseModel):
    course_id: str
    coursework_id: str
    title: Optional[str] = "KnowLedge Verification"


@router.post("/attach")
async def create_attachment(
    req: AttachRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Called by the teacher (or Classroom webhook) when they add KnowLedge to an
    assignment. Requires the teacher's OAuth Bearer token in the Authorization
    header (obtained via the teacher OAuth flow).

    Creates an add-on attachment with:
      - teacherViewUri  → /classroom/teacher-view
      - studentViewUri  → /classroom/student-view
      - studentWorkReviewUri → /classroom/review
    Returns the full Classroom attachment resource.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing teacher Bearer token. Complete the teacher OAuth flow first."
        )
    teacher_token = authorization.removeprefix("Bearer ").strip()

    try:
        attachment = await classroom_client.create_attachment(
            course_id=req.course_id,
            coursework_id=req.coursework_id,
            teacher_token=teacher_token,
            base_url=config.APP_BASE_URL,
            title=req.title or "KnowLedge Verification",
        )
        logger.info(
            f"[attach] Created attachment {attachment.get('id')} "
            f"on course={req.course_id} coursework={req.coursework_id}"
        )
        return {"status": "ok", "attachment": attachment}
    except Exception as e:
        logger.error(f"[attach] Classroom API error: {e}")
        raise HTTPException(status_code=502, detail=f"Classroom API error: {e}")


# ── Teacher OAuth (separate from student) ─────────────────────────────────────

@router.get("/auth/teacher-login")
async def teacher_oauth_login(request: Request, next: str = "/classroom/teacher-view"):
    """Redirects teacher to Google OAuth consent screen (teacher scopes)."""
    params = urllib.parse.urlencode({
        "client_id":     config.GOOGLE_CLIENT_ID,
        "redirect_uri":  f"{config.APP_BASE_URL}/classroom/auth/teacher-callback",
        "response_type": "code",
        "scope":         TEACHER_SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         next,
    })
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/auth/teacher-callback")
async def teacher_oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query("/classroom/teacher-view"),
):
    """
    Exchanges auth code for teacher tokens. Stores under student_id='__teacher__'
    so classroom_client can look them up for attachment creation.
    """
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code":          code,
            "client_id":     config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri":  f"{config.APP_BASE_URL}/classroom/auth/teacher-callback",
            "grant_type":    "authorization_code",
        })
        resp.raise_for_status()
        token_data = resp.json()

    classroom_client.store_token(
        student_id="__teacher__",  # sentinel key for the teacher token
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        expires_in=token_data.get("expires_in", 3600),
    )
    response = RedirectResponse(url=state)
    response.set_cookie("teacher_authed", "1", httponly=True, samesite="lax")
    return response


# ── OAuth Flow ─────────────────────────────────────────────────────────────────

@router.get("/auth/login")
async def oauth_login(request: Request, next: str = "/classroom/student-view"):
    """Redirects student to Google OAuth consent screen."""
    params = urllib.parse.urlencode({
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": f"{config.APP_BASE_URL}/classroom/auth/callback",
        "response_type": "code",
        "scope": STUDENT_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": next,
    })
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/auth/callback")
async def oauth_callback(request: Request, code: str = Query(...), state: str = Query("/")):
    """
    Exchanges auth code for tokens and stores them.
    Redirects to the original destination (usually /classroom/student-view).
    """
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": f"{config.APP_BASE_URL}/classroom/auth/callback",
            "grant_type": "authorization_code",
        })
        resp.raise_for_status()
        token_data = resp.json()

    # Get student's Google ID
    async with httpx.AsyncClient() as client:
        info_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )
        info_resp.raise_for_status()
        user_info = info_resp.json()

    student_id = user_info["sub"]  # Google's stable user ID
    classroom_client.store_token(
        student_id=student_id,
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        expires_in=token_data.get("expires_in", 3600),
    )

    response = RedirectResponse(url=state)
    response.set_cookie("student_id", student_id, httponly=True, samesite="lax")
    return response


# ── Add-on Views ───────────────────────────────────────────────────────────────

@router.get("/teacher-view", response_class=HTMLResponse)
async def teacher_view(request: Request):
    """Teacher-side configuration view shown inside Classroom."""
    return request.app.state.templates.TemplateResponse(
        request, "teacher_view.html", {}
    )


@router.get("/student-view", response_class=HTMLResponse)
async def student_view(request: Request):
    """
    Student-side iframe loaded inside the Classroom assignment page.
    Checks auth; redirects to OAuth if not authenticated.
    """
    student_id = request.cookies.get("student_id")
    if not student_id:
        next_url = urllib.parse.quote(str(request.url))
        return RedirectResponse(url=f"/classroom/auth/login?next={next_url}")

    # Grab Classroom context from query params injected by Classroom
    course_id      = request.query_params.get("courseId", "")
    coursework_id  = request.query_params.get("itemId", "")
    attachment_id  = request.query_params.get("attachmentId", "")
    submission_id  = request.query_params.get("submissionId", "")

    return request.app.state.templates.TemplateResponse(
        request, "student_iframe.html", {
            "student_id":     student_id,
            "course_id":      course_id,
            "coursework_id":  coursework_id,
            "attachment_id":  attachment_id,
            "submission_id":  submission_id,
        }
    )


@router.get("/review", response_class=HTMLResponse)
async def review_view(request: Request):
    """Teacher review URI — shows the student's clearing history for an assignment."""
    session_id = request.query_params.get("sessionId", "")
    session = db.get_classroom_session(session_id) if session_id else None
    return request.app.state.templates.TemplateResponse(
        request, "teacher_view.html", {"session": session}
    )


# ── Unlock Endpoint ────────────────────────────────────────────────────────────

@router.post("/unlock/{session_id}")
async def unlock_submission(session_id: str):
    """
    Called by the frontend (via postMessage relay or direct fetch) when Sage
    marks a concept as cleared. Patches Classroom to allow Turn In.
    """
    session = db.get_classroom_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] == "cleared":
        return {"status": "already_cleared"}

    if not all([session.get("course_id"), session.get("attachment_id"), session.get("submission_id")]):
        # No Classroom IDs yet — just mark locally (standalone mode)
        db.update_session_status(session_id, "cleared")
        return {"status": "cleared_local"}

    try:
        await classroom_client.patch_submission_state(
            course_id=session["course_id"],
            coursework_id=session["assignment_id"],
            attachment_id=session["attachment_id"],
            submission_id=session["submission_id"],
            student_id=session["student_id"],
            state=classroom_client.STATE_TURNED_IN,
        )
        db.update_session_status(session_id, "cleared")
        return {"status": "cleared", "classroom_patched": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Classroom API error: {e}")
