import json
from typing import Dict, Any

import httpx

from .. import config
from .. import db
from .aggregator import build_weekly_payload


def _network_allowed() -> bool:
    # Placeholder. In this deployment, we treat connectivity as allowed.
    # A stricter Wi-Fi check can be injected here per platform.
    if not config.SYNC_ON_WIFI_ONLY:
        return True
    return True


def _post_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    with httpx.Client(timeout=8.0) as client:
        resp = client.post(config.UNIVERSITY_SERVER_URL, json=payload)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": "ok"}


def send_weekly_payload() -> Dict[str, Any]:
    payload = build_weekly_payload()
    if not _network_allowed():
        db.queue_sync_payload(
            course_id=payload["course_id"],
            week=payload["week"],
            payload_json=json.dumps(payload),
            payload_hash=payload["payload_hash"],
            last_error="network_not_allowed",
        )
        db.write_sync_audit(payload["course_id"], payload["week"], len(payload["concepts"]), payload["payload_hash"], "queued", False)
        return {"status": "queued", "reason": "network_not_allowed", "payload": payload}

    try:
        ack = _post_payload(payload)
        db.write_sync_audit(payload["course_id"], payload["week"], len(payload["concepts"]), payload["payload_hash"], "sent", True)
        return {"status": "sent", "payload": payload, "ack": ack}
    except Exception as e:
        db.queue_sync_payload(
            course_id=payload["course_id"],
            week=payload["week"],
            payload_json=json.dumps(payload),
            payload_hash=payload["payload_hash"],
            last_error=str(e),
        )
        db.write_sync_audit(payload["course_id"], payload["week"], len(payload["concepts"]), payload["payload_hash"], "failed", False)
        return {"status": "failed", "error": str(e), "payload": payload}


def retry_pending_sync() -> Dict[str, Any]:
    pending = db.get_pending_sync_payloads()
    sent = 0
    failed = 0
    for row in pending:
        try:
            payload = json.loads(row["payload_json"])
            _post_payload(payload)
            db.write_sync_audit(payload.get("course_id", ""), payload.get("week", ""), len(payload.get("concepts", [])), payload.get("payload_hash", ""), "retry_sent", True)
            db.remove_pending_sync(row["id"])
            sent += 1
        except Exception as e:
            db.write_sync_audit(row.get("course_id", ""), row.get("week", ""), 0, row.get("payload_hash", ""), f"retry_failed:{str(e)[:40]}", False)
            failed += 1
    return {"status": "ok", "pending_total": len(pending), "sent": sent, "failed": failed}
