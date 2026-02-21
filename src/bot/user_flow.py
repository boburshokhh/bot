"""User flow helpers: require user (with timezone) or ask once."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import tz_keyboard, onboarding_time_keyboard
from src.bot.states import OnboardingStates
from src.bot.text import TIMEZONE_CHOOSE_PROMPT
from src.services.user import get_or_create_user, get_user_by_telegram_id

if TYPE_CHECKING:
    from src.db.models import User


class AnswerTarget(Protocol):
    """Object that can send a reply (Message or Chat)."""

    async def answer(self, text: str, reply_markup=None, **kwargs) -> None: ...


async def get_user_or_run_onboarding(
    session: AsyncSession,
    telegram_id: int,
    answer_target: AnswerTarget,
    state: FSMContext | None = None,
) -> User | None:
    """
    Return user if they exist and finished onboarding. Otherwise create/fetch user,
    determine next onboarding step, send prompt, set FSM state, and return None.
    """
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        user = await get_or_create_user(session, telegram_id)

    if not user.onboarding_tz_confirmed:
        if state:
            await state.set_state(OnboardingStates.awaiting_timezone)
        await answer_target.answer(
            TIMEZONE_CHOOSE_PROMPT,
            reply_markup=tz_keyboard(include_detect=True),
        )
        return None

    if not user.onboarding_morning_confirmed:
        if state:
            await state.set_state(OnboardingStates.awaiting_morning_time)
        default_time = user.notify_morning_time.strftime('%H:%M')
        await answer_target.answer(
            f"Во сколько присылать запрос плана утром? (сейчас {default_time})\nВведи время в формате HH:MM или нажми кнопку ниже.",
            reply_markup=onboarding_time_keyboard(default_time),
        )
        return None

    if not user.onboarding_evening_confirmed:
        if state:
            await state.set_state(OnboardingStates.awaiting_evening_time)
        default_time = user.notify_evening_time.strftime('%H:%M')
        await answer_target.answer(
            f"Во сколько присылать вечернюю сверку? (сейчас {default_time})\nВведи время в формате HH:MM или нажми кнопку ниже.",
            reply_markup=onboarding_time_keyboard(default_time),
        )
        return None

    return user
