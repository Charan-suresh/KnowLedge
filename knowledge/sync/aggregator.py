import hashlib
import json
from datetime import UTC, datetime
from typing import Dict, Any, List

from .. import config
from .. import db


def current_week_label(now: datetime | None = None) -> str:
    dt = now or datetime.now(UTC)
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def _concept_record(row: Dict[str, Any]) -> Dict[str, Any]:
    # Privacy guard: do not include source_text, chat history, or typing metrics.
    return {
        "concept": row.get("concept", ""),
        "status": row.get("status", "on_loan"),
        "clearing_method": row.get("clearing_method") or "",
        "lens_signature": row.get("lens_signature") or "",
        "integrity_suspect": bool(row.get("integrity_suspect", 0)),
    }


def build_weekly_payload() -> Dict[str, Any]:
    rows = db.list_sync_concepts()
    concepts: List[Dict[str, Any]] = [_concept_record(r) for r in rows]
    payload = {
        "course_id": config.COURSE_ID,
        "week": current_week_label(),
        "concepts": concepts,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload["payload_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload
