"""Common: errors, logging."""
import logging

from aiogram import Router
from aiogram.types import ErrorEvent

router = Router()
logger = logging.getLogger(__name__)


@router.error()
async def error_handler(event: ErrorEvent):
    logger.exception(
        "Update %s caused error: %s",
        event.update,
        event.exception,
        extra={"request_id": event.update.update_id},
    )
    return True  # suppress propagation
