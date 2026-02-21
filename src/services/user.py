"""User registration and settings."""
from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return r.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    r = await session.execute(select(User).where(User.id == user_id))
    return r.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    *,
    timezone: str = "UTC",
    notify_morning_time: time | None = None,
    notify_evening_time: time | None = None,
) -> User:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        return user
    user = User(
        telegram_id=telegram_id,
        timezone=timezone,
        notify_morning_time=notify_morning_time or time(7, 0),
        notify_evening_time=notify_evening_time or time(21, 0),
    )
    session.add(user)
    await session.flush()
    return user


async def update_user_timezone(session: AsyncSession, user_id: int, timezone: str) -> User | None:
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    user.timezone = timezone
    await session.flush()
    return user


async def update_onboarding_flags(
    session: AsyncSession,
    user_id: int,
    *,
    tz_confirmed: bool | None = None,
    morning_confirmed: bool | None = None,
    evening_confirmed: bool | None = None,
) -> User | None:
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    if tz_confirmed is not None:
        user.onboarding_tz_confirmed = tz_confirmed
    if morning_confirmed is not None:
        user.onboarding_morning_confirmed = morning_confirmed
    if evening_confirmed is not None:
        user.onboarding_evening_confirmed = evening_confirmed
    await session.flush()
    return user


async def update_notify_times(
    session: AsyncSession,
    user_id: int,
    *,
    notify_morning_time: time | None = None,
    notify_evening_time: time | None = None,
) -> User | None:
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    if notify_morning_time is not None:
        user.notify_morning_time = notify_morning_time
    if notify_evening_time is not None:
        user.notify_evening_time = notify_evening_time
    await session.flush()
    return user


async def update_morning_reminder_settings(
    session: AsyncSession,
    user_id: int,
    *,
    interval_minutes: int | None = None,
    max_attempts: int | None = None,
) -> User | None:
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    if interval_minutes is not None:
        user.morning_reminder_interval_minutes = interval_minutes
    if max_attempts is not None:
        user.morning_reminder_max_attempts = max_attempts
    await session.flush()
    return user
