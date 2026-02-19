"""User flow helpers: require user (with timezone) or ask once."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import tz_keyboard
from src.bot.text import TIMEZONE_CHOOSE_PROMPT
from src.services.user import get_or_create_user, get_user_by_telegram_id

if TYPE_CHECKING:
    from src.db.models import User


class AnswerTarget(Protocol):
    """Object that can send a reply (Message or Chat)."""

    async def answer(self, text: str, reply_markup=None, **kwargs) -> None: ...


async def get_user_or_ask_timezone(
    session: AsyncSession,
    telegram_id: int,
    answer_target: AnswerTarget,
) -> User | None:
    """
    Return user if they exist in DB (timezone already stored). Otherwise create user
    with UTC, send timezone choice once, and return None so the handler exits.
    """
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is not None:
        return user
    await get_or_create_user(session, telegram_id)
    await answer_target.answer(
        TIMEZONE_CHOOSE_PROMPT,
        reply_markup=tz_keyboard(include_detect=True),
    )
    return None
