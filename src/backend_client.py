import logging
import requests
from .config import BACKEND_BASE_URL, ROBOT_ID
from .models import ApprovalState

_notified_pending = False

def notify_pending_if_needed(update_pending: bool, update_downloaded: bool) -> None:
    global _notified_pending
    if not BACKEND_BASE_URL or not ROBOT_ID:
        return
    if not update_pending or _notified_pending:
        return

    url = f"{BACKEND_BASE_URL}/robots/{ROBOT_ID}/updates/pending"
    payload = {
        "update_pending": update_pending,
        "update_downloaded": update_downloaded,
    }
    requests.post(url, json=payload, timeout=5).raise_for_status()
    _notified_pending = True
    logging.info("Backend notificado de update pendiente")

def get_approval() -> ApprovalState:
    if not BACKEND_BASE_URL or not ROBOT_ID:
        return ApprovalState(approved=False)

    url = f"{BACKEND_BASE_URL}/robots/{ROBOT_ID}/updates/approval"
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    data = response.json()
    return ApprovalState(
        approved=bool(data.get("approved", False)),
        approved_by=data.get("approved_by"),
        approved_at=data.get("approved_at"),
    )