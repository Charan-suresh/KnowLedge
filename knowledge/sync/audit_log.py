from typing import List, Dict, Any

from .. import db


def get_sync_audit() -> List[Dict[str, Any]]:
    return db.get_sync_audit_log()
