"""
classroom_client.py
Thin async wrapper around the Google Classroom API.
All calls use the student's stored OAuth token from the database.

TODO: Before deploying, set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
      in config.py (or via environment variables).
"""

import httpx
import json
from datetime import datetime, timezone
from typing import Optional
from . import db
from . import config

CLASSROOM_BASE = "https://classroom.googleapis.com/v1"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

# Classroom Add-on attachment student work states
STATE_UNSUBMITTED = "STUDENT_UNSUBMITTED_WORK_STATE_UNSPECIFIED"
STATE_IN_PROGRESS  = "STUDENT_SUBMISSION_STATE_IN_PROGRESS"
STATE_TURNED_IN    = "TURNED_IN"


async def _get_valid_token(student_id: str) -> str:
    """
    Returns a valid access token for student_id.
    Refreshes automatically if expired.
    """
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT access_token, refresh_token, expires_at FROM oauth_tokens WHERE student_id = ?",
            (student_id,)
        ).fetchone()

    if not row:
        raise ValueError(f"No OAuth token stored for student_id={student_id!r}. "
                         "Student must complete the OAuth flow first.")

    # Check expiry (with 60-second buffer)
    expires_at = datetime.fromisoformat(row["expires_at"]).replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc).timestamp() + 60 < expires_at.timestamp():
        return row["access_token"]

    # Refresh the token
    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_ENDPOINT, data={
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "refresh_token": row["refresh_token"],
            "grant_type": "refresh_token",
        })
        resp.raise_for_status()
        data = resp.json()

    new_access = data["access_token"]
    new_expiry = datetime.now(timezone.utc).timestamp() + data.get("expires_in", 3600)

    with db.get_connection() as conn:
        conn.execute(
            "UPDATE oauth_tokens SET access_token=?, expires_at=? WHERE student_id=?",
            (new_access, datetime.fromtimestamp(new_expiry, tz=timezone.utc).isoformat(), student_id)
        )

    return new_access


async def create_attachment(
    course_id: str,
    coursework_id: str,
    teacher_token: str,
    base_url: str,
    title: str = "KnowLedge Verification"
) -> dict:
    """
    Creates an add-on attachment on an assignment.
    Uses the teacher's token (from OAuth flow at assignment creation time).
    Returns the full attachment resource dict.
    """
    url = f"{CLASSROOM_BASE}/courses/{course_id}/courseWork/{coursework_id}/addOnAttachments"
    payload = {
        "teacherViewUri": {"uri": f"{base_url}/classroom/teacher-view"},
        "studentViewUri": {"uri": f"{base_url}/classroom/student-view"},
        "studentWorkReviewUri": {"uri": f"{base_url}/classroom/review"},
        "title": title,
        "maxPoints": 0,  # ungraded gate
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        resp.raise_for_status()
        return resp.json()


async def patch_submission_state(
    course_id: str,
    coursework_id: str,
    attachment_id: str,
    submission_id: str,
    student_id: str,
    state: str = STATE_TURNED_IN
) -> dict:
    """
    Updates the studentWorkRevisionState on the student's attachment submission.
    A state of TURNED_IN unblocks the Classroom Turn-In button.
    """
    token = await _get_valid_token(student_id)
    url = (
        f"{CLASSROOM_BASE}/courses/{course_id}"
        f"/courseWork/{coursework_id}"
        f"/addOnAttachments/{attachment_id}"
        f"/studentSubmissions/{submission_id}"
    )
    payload = {"studentWorkRevisionState": state}
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            url,
            json=payload,
            params={"updateMask": "studentWorkRevisionState"},
            headers={"Authorization": f"Bearer {token}"}
        )
        resp.raise_for_status()
        return resp.json()


async def get_submission_id(
    course_id: str,
    coursework_id: str,
    student_id: str,
) -> Optional[str]:
    """
    Looks up the student's submissionId for a given assignment.
    Required before patching submission state.
    """
    token = await _get_valid_token(student_id)
    url = f"{CLASSROOM_BASE}/courses/{course_id}/courseWork/{coursework_id}/studentSubmissions"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            params={"userId": "me"},
            headers={"Authorization": f"Bearer {token}"}
        )
        resp.raise_for_status()
        submissions = resp.json().get("studentSubmissions", [])
        return submissions[0]["id"] if submissions else None


def store_token(student_id: str, access_token: str, refresh_token: str, expires_in: int):
    """Persists an OAuth token set to the database."""
    from datetime import timedelta
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO oauth_tokens (student_id, access_token, refresh_token, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                access_token=excluded.access_token,
                refresh_token=excluded.refresh_token,
                expires_at=excluded.expires_at
        """, (student_id, access_token, refresh_token, expires_at))
