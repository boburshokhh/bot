"""Middlewares: request_id, db session, validation."""
import logging
import uuid
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.db import async_session_factory

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseMiddleware):
    """Set request_id in data and log."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        request_id = str(uuid.uuid4())[:8]
        data["request_id"] = request_id
        logger.info("request_id=%s", request_id, extra={"request_id": request_id})
        return await handler(event, **data)


class DbSessionMiddleware(BaseMiddleware):
    """Inject async DB session into handler data. Session is committed on success, rolled back on error."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not async_session_factory:
            return await handler(event, **data)
        async with async_session_factory() as session:
            data["session"] = session
            try:
                result = await handler(event, **data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
