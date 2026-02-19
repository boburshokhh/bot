"""Notification logging for morning/evening sends and retries."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import NotificationLog

TYPE_MORNING = "morning"
TYPE_EVENING = "evening"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_RETRIED = "retried"


async def log_notification(
    session: AsyncSession,
    user_id: int,
    notif_type: str,
    status: str,
    payload: dict[str, Any] | None = None,
) -> NotificationLog:
    log = NotificationLog(
        user_id=user_id,
        type=notif_type,
        status=status,
        payload=payload,
    )
    session.add(log)
    await session.flush()
    return log
